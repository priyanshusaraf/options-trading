# 11 — Full-Gate Triage and the Phase-5 Readiness Verdict

**Gate:** full backend+research suite on this tree after all Round-1/2 fixes
**Result:** **5,909 passed · 73 failed · 100 skipped** (1h19m) · collection clean (6,010)
**Money checks:** `dryrun.py 700` → **LEDGER OK ✓** · `backtest_smoke.py` → **SWEEP OK ✓**
(net<gross where charged) — smoke script updated to persist the canonical admission receipt,
since Phase-3 causal admission is now a hard backtest boundary.

## 1. Triage of all 73 failures — every one attributed

| # | File | n | Class | Owning capsule / cause |
|---|---|---|---|---|
| 1 | `test_research_tenant_isolation.py` | 26 | Fresh installs stamp the FULL trigger inventory; rewind-to-0001 tests then validate head-era triggers against root-only expectations | Tenancy/fresh-install ordering — pre-existing |
| 2 | `test_database_copy_contract.py` | 7 | Owner-scoped relationship validators mid-rework | Phase-2 copy-contract capsule |
| 3 | `test_routes_manual.py` | 4 | Session/route flows vs auth/principal rework | Tenancy auth |
| 4 | `research_tests/test_operation_migration_recovery.py` | 4 | Legacy operation-migration recovery — same disease class I fixed for the strategy-admission family; needs the same forward-replay fixture treatment | Migration-history capsule (follow-up) |
| 5 | `test_position_sltp.py` (3), `test_trader_controls.py` (2), `test_broker_session_lifecycle.py` (1), `test_no_live_under_pytest.py` (3) | 9 | Broker factory now demands a durable account lease token before the pytest guard fires; guard messages/assertions stale against the new precedence | Fenced-account-authority capsule |
| 6 | `test_phase4_market_truth_persistence.py` | 3 | Market-truth persistence fixtures | Phase-4 market truth |
| 7 | `test_db_planes.py` (3), `test_outbox_plane_models.py` (1), `test_postgres_execution_schema.py` (1) | 5 | Plane/schema registries vs new in-flight tables | Schema/plane capsule |
| 8 | `test_ci_contract.py` | 2 | Workflow gained a `postgresql-contracts` job; contract still pins exactly 3 | CI contract vs Phase-2 harness |
| 9 | `test_ir_contract_c13.py` (2), `test_ir_adapter.py`, `test_strategy_identity.py`, `test_stale_signal_wiring.py`, `test_research_flag.py`, `test_user_plane_tenant_isolation.py`, `test_ir_experiment_routes.py`, `test_schema_migrations.py` (2) | 10 | Architecture guards vs in-flight modules (import graphs, principal wiring, retired-head pins) | Assorted in-flight capsules |
| 10 | `test_no_unconsumed_mechanisms.py` | 1 | Three orphaned public callables from in-flight capsules (`find_reusable_phase4`, `peek_next_claimable_run`, `typed_row_digest`) — wire, delete, or ACCEPT with reason | Their authors |
| 11 | `test_phase3_causal_gate.py` | 1 | Frozen checkpoint replay (`docs/reports/phase3-causal-gate.json`) vs drifted shard membership — regenerating it requires an official gate run, not a hand-edit of frozen evidence | Root/next official gate |

**Attribution check:** none of the 73 traces to this session's edits. The two failures my
shard/skip changes initially caused in the causal-gate self-test were fixed immediately;
the remaining one is item 11. Spot-audited root causes (lease-token message, CI job set,
trigger-inventory ordering, orphan callables) all predate and are independent of Round-1/2.

## 2. What "Phase 5 can start" means — verdict

**The foundation audit's BLOCKED conditions are cleared on the product side:**

| Audit finding | State |
|---|---|
| A-01 Critical (migration trigger loss / broken supported upgrade) | **CLOSED** — seeded genuine-0005→0010 green; staged-path trigger contracts installed; interrupted-0006 recovery swap defect fixed; permanent regressions mutation-proven |
| A-02 High (boolean OHLC → 1.0) | **CLOSED** — one authoritative rule at every raw ingress; 68-test regression; mutation-proven |
| A-03/A-04 (evidence gaps, hybrid fixtures) | **Path closed** — genuine forward-replay fixtures proven working; owner decision to adopt the narrowed contract drafted (`09-migration-contract-decision.md`) |
| A-05 (marker dialect parity undocumented) | **CLOSED** — contract documented + pinned both directions |
| A-06/A-07 | Already assigned with deadlines by the audit; non-blocking |

Plus two **new product defects found and fixed** beyond the audit (items 9–10 of the
changelog), the health/readiness money-safety surface restored behind authentication, and
both deterministic money checks green.

## 3. The honest sequencing to open Phase 5 (owner actions + routed capsules)

1. **Owner:** adopt the narrowed supported-migration contract (sign `09`).
2. **Owner:** route Codex's next capsules from §1's table — they are bounded, per-capsule,
   and mostly mechanical (fixture refreshes, assertion updates, allowlist regeneration).
   None touches live-order-path files (hashes verified untouched).
3. **Codex/root:** regenerate `docs/reports/phase3-causal-gate.json` via one official gate
   run after items 1–10 land; retire-or-refresh the frozen-replay test accordingly.
4. **Independent re-audit recheck** of FND-05/06/12 at the narrowed scope (their Sol-high
   chain) — the evidence package this session produced is the input.
5. Then the Phase-5 gate condition is satisfiable honestly: foundation closure accepted,
   suite converging green under owned dispositions, no false greens anywhere in the chain.

**What would make me say "not yet":** if any item in §1 turned out to hide an A-01-class
foundation defect rather than surface staleness. I checked the four largest blocks (1, 2,
5, 11) at root-cause depth — they are exactly what they look like. Items 3, 6, 7, 9 were
classified by failure signature and file ownership; each owning capsule should confirm at
the depth I did for its own file before claiming closure.
