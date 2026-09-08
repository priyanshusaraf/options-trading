# 02 — Claim-by-Claim Verification of the Codex Run Summary

**Method:** every claim was checked directly against files in the worktree at HEAD `de6faae`
(+ dirty tree) on 2026-08-21. Verdicts: VERIFIED / PARTIAL / REFUTED / UNVERIFIABLE.

## Summary table

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | "16 registered systemic defect patterns" | **VERIFIED** | `DEFECT_PATTERNS.md` — exactly DP-001…DP-016 |
| 2 | Audit findings A-01…A-07 and severities | **VERIFIED** | `.agent/runs/phase1-4-foundation-audit/report.md` |
| 3 | Recovery 9 preaudit binds 8 rejections; oracle = 22 cases / 28 mutations / 8 replays / 2 relocation roots | **VERIFIED** | `harness-replacement-recovery-9-consolidated-preaudit.json` fields match exactly |
| 4 | CURRENT.md: status blocked, phase interphase-4-5, stage phase1-4-foundation-critical-closure | **VERIFIED** | `CURRENT.md` lines 4–7 |
| 5 | Finite lifecycle INITIAL_COMPLETE → ROOT_ACCEPTED | **VERIFIED** | recovery-9 capsule line 12 (stopping condition); PROGRAMME.json policies |
| 6 | Timezone + JSON-dialect defects closed on named surfaces | **VERIFIED** | `app/market_data/observations.py`, `dataset_authority.py` (canonical instant logic); `research/domain/migrations/0010_research_json_shape_parity.py` exists |
| 7 | Boolean OHLC: `True` becomes executable `1.0` | **VERIFIED at code level** | see §2 below |
| 8 | PostgreSQL cleanup once treated nonzero status as "server absent"; found+rejected | **PARTIAL** | `scripts/run_disposable_postgres.py` contains the pg_ctl stop/removal logic and cleanup-recovery logs exist; I did not locate the exact defective line by grep. Consistent, not independently reproduced |
| 9 | Programme state: 82 stages, current = foundation-critical-closure, later phases blocked | **VERIFIED** | `PROGRAMME.json` parsed: current_stage_id matches; stages 77–82 (Phase 9/10/release review) all `"blocked"`; controller gpt-5.6-luna / 120-min cadence |
| 10 | "I would not put money into this application today… paper only" | **VERIFIED (consistent)** | frozen preaudit records `real_money_posture = NO_RESEARCH_AND_PAPER_ONLY` |
| 11 | ~322 dirty entries at audit time | **VERIFIED AND WORSE** | now **374**; tracked diff alone is 162 files, +12,226/−1,523 |
| 12 | Protected product files unchanged | **VERIFIED** | all four SHA-256s match the frozen audit values byte-for-byte |

## Detail on the load-bearing checks

### Defect pattern register (claim 1)

`paper-trader/docs/agent/DEFECT_PATTERNS.md` contains precisely sixteen `## DP-0NN` sections:
DP-001 distinct-facts-collapsed · DP-002 syntactic-self-consistency-as-authority · DP-003 mocked
seam as lifecycle evidence · DP-004 immutable envelope over mutable facts · DP-005 address-bearing
metadata as typed fact · DP-006 session timezone changed copied instants · DP-007 JSON helper
encoded differently per dialect · DP-008 manual prerequisite verification instead of consuming seam ·
DP-009 logical ORM transaction mistaken for physical transaction · DP-010 current-head/hybrid
fixtures as supported-old evidence · DP-011 host numeric subtypes cross typed market boundary ·
DP-012 producer-chosen fixture baseline · DP-013 prose fixture roles as topology authority ·
DP-014 predicate-family presence as witness authority · DP-015 single-parent traversal as complete
ancestry · DP-016 final assurance consumes evidence before its producer creates it.
All are Critical or conditional-Critical. The register's own status rules require root-cause +
prevention invariant + permanent adversarial regression + transitive revalidation for closure —
the claims about *what closure requires* are accurate.

### Foundation audit (claim 2)

Verified verbatim from the report: FND-06 migration integrity `FAIL, Critical`; FND-09 closed
numeric validity `FAIL, High` ("raw OHLC validation converts True to executable 1.0"); FND-13
claim/reclaim/finalization `INTENTIONALLY UNPROVED`; FND-14 paper/live/provider separation
`CLOSED NON-ENABLEMENT BOUNDARY`; FND-15 deployability `NOT PROVED`. A-01..A-07 severities match
the summary exactly, including the "checked only four of twenty-four caller tables" false-green
(the same fact appears in `CURRENT.md`'s scope decisions).

### Recovery 9 preaudit (claim 3)

The frozen JSON declares: `historical_rejection_count = 8`,
`candidate_case_count = 22`, `mutation_count = 28`, `relocation_root_count = 2`,
7 material findings (`R9-PRE-001..007`),
`decision = AUTHORIZE_SINGLE_CONSOLIDATED_REPAIR`, `status =
FROZEN_REJECTED_PREAUDIT_REPAIR_WINDOW_OPEN`, `attempt_budget.third_package_patch_authorized =
false`, and a reserved-but-unactivated successor capsule (`...correction-4...`). The eight
historical rejection classes in the summary map onto the audit scripts present under
`.agent/runs/phase1-4-foundation-critical-closure/root/` (recovery 2/3/4/6 package audits,
recovery 7/8 frozen-package rejections, correction-3 repeated-failure audit).

### The omission the summary did not mention

**The full backend suite currently fails at collection on this tree:**

```
ERROR tests/test_foundation_research_projection_contracts.py
  ImportError: cannot import name 'DeclaredNativeAdapter'
    from 'tests.foundation_native_state_contract'   (test file line 26)
ERROR tests/test_phase3_causal_gate.py
  RuntimeError: slow-shard replacement drifted for broad_tests_15
    (scripts/phase3_causal_gate.py:389 in _replace_proven_slow_shard)
```

Both errors are symptoms of mid-flight capsule work (a test module written against a helper API
that does not exist yet; a shard-replacement guard detecting drift), not product regressions —
but they mean **no one can currently verify any green/red claim on current bytes**, and the
Recovery 9 repair will be built on a tree whose own suite cannot run end-to-end. This belongs in
the risk register above the harness itself.

### Protected files (claim 12)

```
kite_venue.py        2fd450b6…99240  MATCH
venue.py             c8a39f0e…25dae  MATCH
brokers.py           d5e6b836…d1d38  MATCH
test_broker_registry 13a174e3…491e3  MATCH
```

The live-order-path perimeter is byte-identical to what the audit froze. Whatever else is in
flight, the money-touching engine files were not touched.

### Boolean ingress (claim 7)

- `app/providers/dhan.py:226-230` — `open=float(columns["open"][i]) … volume=float(columns["volume"][i])`.
  In Python `bool ⊂ int`, so `float(True) == 1.0` passes straight through. Note also
  `dhan.py:191`: `isinstance(px, (int, float))` accepts `True`.
- `app/backtest/dataset_store.py:646-648` — `struct.pack(">q5d", _timestamp_us(ts),
  float(candle.open), float(candle.high), …)` — the dataset encoder boundary the audit described.
- DP-011 documents the pattern with the required prevention invariant (reject bool before
  coercion at every raw numeric ingress, one authoritative rule across provider → preparation →
  storage → identity → evaluation → sizing → execution).

## What this verification changes

Nothing about the Codex summary's honesty — it holds. It changes the *priority stack*: the
summary treats the harness as the frontier and the tree as background. The tree state (374 dirty
entries, uncollectable suite) is actually the frontier, because every other activity — including
Recovery 9's consolidated repair — depends on those bytes being durable and the suite being
runnable.
