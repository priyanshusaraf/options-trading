---
{
  "id": "strategy-os-v1-causal-research-benchmark-spec",
  "phase": "v1-planning",
  "status": "planning_complete_rebase_required",
  "kind": "causal_research_golden_benchmark_specification",
  "source_thread_id": "01a04c7c-257a-7210-9dd3-f639c661db00",
  "goal": "Specify source-independent golden fixtures and falsifiable failure hypotheses for causal research without changing or pre-accepting V0 product behavior.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The capsule and its four evidence artifacts name exact fixture inputs, causal cutoffs, expected invariants or typed refusals, reversible mutations, cold-restart reproducibility receipts and one future implementation owner for every requested benchmark; the diff contains no product, test, cache, schema, runtime, programme or current-stage change."
  },
  "risk_tags": [
    "important",
    "research-integrity",
    "causality",
    "point-in-time-data",
    "historical-derivatives-refusal",
    "semantic-identity",
    "net-of-charges",
    "oos-separation",
    "reconstruction"
  ],
  "planning_base": {
    "sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "branch": "codex/execution-foundation",
    "authority": "source-independent planning reference only",
    "worktree_claim": "No clean-worktree claim. The authoritative V0 worktree was dirty; only the new capsule and isolated ignored evidence path were writable."
  },
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v1-parallelization-audit/safe-now-capsule-queue.json",
      "sections": [
        "capsules[id=strategy-os-v1-causal-research-benchmark-spec]"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v1-parallelization-audit/report.md",
      "sections": [
        "Outcome",
        "Minimum canonical contracts",
        "Safe-now and blocked work",
        "Deployment impact and nonclaims"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v1-parallelization-audit/branch-merge-plan.md",
      "sections": [
        "Base and naming",
        "Ownership and freeze rules",
        "Cadence",
        "Merge-back prerequisites by collision class"
      ]
    }
  ],
  "dependency_gate": "The owner authorized this specification-only packet. Product implementation remains blocked until V0_FREEZE_SHA exists, the packet is rebased onto it, and frozen V0 research, dataset, instrument, charge, refusal, OOS and benchmark vocabularies are mapped by exact content address.",
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v1-causal-research-benchmark-spec.md",
    ".agent/runs/strategy-os-v1-causal-research-benchmark-spec"
  ],
  "evidence_outputs": [
    ".agent/runs/strategy-os-v1-causal-research-benchmark-spec/benchmark-matrix.json",
    ".agent/runs/strategy-os-v1-causal-research-benchmark-spec/fixture-specification.md",
    ".agent/runs/strategy-os-v1-causal-research-benchmark-spec/mutation-plan.md",
    ".agent/runs/strategy-os-v1-causal-research-benchmark-spec/report.md"
  ],
  "protected_paths": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/programme",
    "paper-trader/docs/agent/tasks (except this capsule)",
    ".codex",
    ".agents",
    "/Users/priyanshusaraf/dev/strategy-os-frontend"
  ],
  "scope": [
    "Define eight golden benchmarks covering point-in-time reference facts, event timing, historical-derivatives refusal, semantic-address binding, point-in-time universe membership, charge/cost identity, OOS separation and first-divergence reconstruction.",
    "Give every benchmark literal fixture inputs, one or more exact UTC causal cutoffs, a closed expected invariant or typed refusal, one falsifiable reversible mutation, a restart/reproducibility receipt contract and a future implementation owner.",
    "Keep observation time, effective time, publication time and correction lineage distinct. Select only facts published no later than the evaluation cutoff.",
    "Bind research requests, cache entries, results and replay receipts to all answer-changing semantic addresses, including dataset, reference/event snapshot, universe snapshot, charge/cost policy, split policy, graph/component implementation and causal cutoff.",
    "Keep selection/training/validation/embargo facts separate from OOS observations and scores.",
    "Require first divergence to identify the earliest unequal causal input or typed missing-lineage refusal, never infer a cause from final PnL alone.",
    "Route later implementation through fresh capsules only after the V0 freeze mapping gate."
  ],
  "benchmark_ids": [
    "CRB-REF-01",
    "CRB-EVT-02",
    "CRB-DERIV-03",
    "CRB-ADDR-04",
    "CRB-UNIV-05",
    "CRB-COST-06",
    "CRB-OOS-07",
    "CRB-DIV-08"
  ],
  "acceptance": [
    "The matrix contains exactly the eight declared benchmark IDs, no duplicate benchmark, fixture or mutation ID, and one non-empty future-owner route for every row.",
    "CRB-REF-01 proves publication-cutoff selection and prefix invariance across a later correction; CRB-EVT-02 proves schedule, reschedule and actual-event facts cannot appear before their own publication times.",
    "CRB-DERIV-03 refuses a historical option request whose exact contract, interval and required OHLCV/OI/bid/ask coverage are not present. Underlying OHLCV, prospective capture and catalogue presence cannot satisfy it.",
    "CRB-ADDR-04 changes request/result/cache identity when one answer-changing semantic address changes and preserves old receipt reconstruction.",
    "CRB-UNIV-05 selects membership as published at each cutoff and never rewrites an earlier universe from terminal membership.",
    "CRB-COST-06 produces exact net Decimal results from the named charge stack and gives different result/cache identities to different cost policies even when gross fills match.",
    "CRB-OOS-07 seals train, validation, embargo and OOS boundaries before selection; OOS rows cannot influence candidate selection or cached selection identity.",
    "CRB-DIV-08 reconstructs the earliest differing causal input and refuses with FIRST_DIVERGENCE_LINEAGE_INCOMPLETE when required trace lineage is absent.",
    "Every mutation is killed by its named future selector, is isolated to one contract defect and requires before/mutated/restored hashes.",
    "Two cold-process runs and one warm-cache replay produce byte-identical canonical result and selected-input receipts where the semantic input set is unchanged; cache-hit metadata remains non-semantic.",
    "Artifact validation proves that only this capsule and the four declared ignored evidence files changed."
  ],
  "test_plan": [
    "Specification stage: validate JSON shape, benchmark/fixture/mutation/owner coverage, internal references, UTC cutoffs, typed-refusal fields and path scope. Do not run or edit product tests.",
    "Future implementation stage: author frozen fixtures before harness code, run each selector RED/GREEN, run its isolated reversible mutation, perform two cold-process runs plus one warm-cache replay, and preserve canonical receipts.",
    "Future integration stage: run the affected frozen V0 research/dataset/cache/charges/robustness suites and one research-integrity review after all eight benchmark selectors pass."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "review": {
    "required": true,
    "assignment_id": "strategy_os_v1_causal_research_benchmark_spec_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "The planning packet fixes causal research, historical-data refusal, semantic identity, net-cost, OOS and reconstruction benchmark contracts that future implementation must not weaken.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v1-causal-research-benchmark-spec/review-package.json",
    "review_paths": [
      "paper-trader/docs/agent/tasks/strategy-os-v1-causal-research-benchmark-spec.md",
      ".agent/runs/strategy-os-v1-causal-research-benchmark-spec"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme",
      ".codex",
      ".agents"
    ],
    "output": ".agent/runs/strategy-os-v1-causal-research-benchmark-spec/review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "future_implementation_routing": {
    "notice": "These are exact routing names for later materialization, not created or authorized capsules.",
    "CRB-REF-01": "strategy-os-v1-5-reference-event-research-runtime",
    "CRB-EVT-02": "strategy-os-v1-5-reference-event-research-runtime",
    "CRB-DERIV-03": "strategy-os-v1-historical-derivatives-capability-contract",
    "CRB-ADDR-04": "strategy-os-v1-causal-research-identity-and-cache",
    "CRB-UNIV-05": "strategy-os-v1-5-point-in-time-universe-runtime",
    "CRB-COST-06": "strategy-os-v1-causal-research-cost-identity",
    "CRB-OOS-07": "strategy-os-v1-robustness-oos-separation",
    "CRB-DIV-08": "strategy-os-v1-research-first-divergence-replay"
  },
  "rebase_contract": {
    "required_base_symbol": "V0_FREEZE_SHA",
    "required_base_value": null,
    "status": "BLOCKED_UNTIL_V0_FREEZE_SHA_EXISTS",
    "timing": [
      "Rebase once immediately before owner review after V0_FREEZE_SHA is published.",
      "Regenerate rather than hand-resolve any semantic conflict in research, dataset, cache, instrument, charge, OOS, refusal or benchmark vocabulary.",
      "Record exact frozen input hashes in a separate future consumption receipt before any product-capable capsule starts."
    ],
    "required_frozen_mappings": [
      "canonical graph/component/implementation and research-request identities",
      "dataset manifest, content digest, causal time and correction lineage",
      "canonical instrument and exact derivative contract identity",
      "typed provider/data-capability refusal vocabulary",
      "research cache and result identity dimensions",
      "static-scope or point-in-time universe snapshot identity",
      "full charge, slippage and cost-policy identity with Decimal rounding",
      "train/validation/embargo/OOS split and robustness-trial identity",
      "evidence-ledger and first-divergence trace vocabulary",
      "accepted V0 golden-benchmark release vocabulary"
    ],
    "failure_rule": "If any fixture assumption cannot map one-to-one to frozen V0 truth, keep the affected benchmark blocked and replan it; do not add a parallel schema, cache key, result identity, refusal code or research ledger."
  },
  "owner_gates": [
    "This task ends at specification and artifact validation.",
    "A fresh capsule and exact V0_FREEZE_SHA consumption receipt are required before tests, fixtures in product paths, cache keys, schemas, runtime code or APIs are changed.",
    "Provider selection, data purchase/licensing, credentials or provider network access require their own data-rights and owner decisions.",
    "Live, order, money, deployment and frontend work remain outside this capsule."
  ],
  "stop_conditions": [
    "V0_FREEZE_SHA is unavailable but product coupling is required.",
    "A benchmark would require an invented second dataset, instrument, research ledger, cache, charge or refusal identity.",
    "Historical option support would be inferred from underlying data, prospective capture, descriptor presence or an unproven provider claim.",
    "Exact input time, source, publication/correction lineage, split boundary or future owner cannot be named.",
    "Any change outside the two allowed paths becomes necessary."
  ],
  "deployment_impact": {
    "classification": "documentation-only planning packet",
    "runtime": false,
    "schema": false,
    "migration": false,
    "cache": false,
    "dependency": false,
    "provider": false,
    "frontend": false,
    "deployment_authority": false
  },
  "nonclaims": [
    "No benchmark has been implemented, run or passed.",
    "No research domain, reference/event source, point-in-time universe or historical derivatives dataset is supported by this packet.",
    "Broad options-history backtesting remains unavailable until exact historical contract/field/interval coverage, rights, correction lineage and provider conformance are proven. Underlying OHLCV and prospective option capture are insufficient.",
    "No backtest eligibility, numeric correctness, cache correctness, OOS robustness, first-divergence reconstruction, release readiness or production readiness is established.",
    "No test, product, fixture cache, schema, migration, runtime, API, dependency, provider, credential, network, frontend, deployment, live, order or money change is authorized or made.",
    "The planning base is not V0_FREEZE_SHA and cannot authorize V1 product work."
  ]
}
---

# Causal research benchmark specification

This source-independent packet fixes eight falsifiable benchmark oracles without changing Strategy OS behavior. The complete matrix, fixture bytes, mutation requirements and planning receipt live under `.agent/runs/strategy-os-v1-causal-research-benchmark-spec/`.

The packet is deliberately blocked from product use. A future owner must rebase it onto the exact accepted `V0_FREEZE_SHA`, map every fixture identity to the frozen V0 contracts and materialize a fresh implementation capsule. If the mapping is not exact, the affected benchmark stays blocked.

Historical options support is not available by implication. Exact underlying bars, a prospective option stream or a catalogue descriptor do not prove broad historical option-contract coverage. The historical-derivatives benchmark therefore expects a typed refusal until supported data and rights are proven.
