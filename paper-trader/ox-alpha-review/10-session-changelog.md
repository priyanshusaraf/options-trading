# 10 — Session Changelog: What ox-alpha Changed and Why

**Session date:** 2026-08-21 · **Base:** worktree `codex-execution-foundation` @ `de6faae`
(+ Codex's uncommitted in-flight state, untouched where possible) · **All changes
test-first with mutation proofs; nothing deployed; no live path touched.**

## The chain of defects found, in discovery order

Each fix below exposed the next — collection was failing in layers.

### 1. Shard-replacement drift (collection blocker #2)

**Symptom:** `RuntimeError: slow-shard replacement drifted for broad_tests_15` at import of
`scripts/phase3_causal_gate.py`.
**Root cause:** new test files (`test_duplicate_order_prevention.py`,
`test_event_risk_engine.py`) shifted the alphabetical shard windows; the hard-coded
sub-shard splits for `broad_tests_15`/`broad_tests_19` no longer matched membership. The
drift guard did exactly its job.
**Fix:** re-anchored both split tables to current membership, preserving timeout tuning
(`intraday_e2e` keeps `SLOW_BROAD_TIMEOUT_SECONDS`; attribution nodeids unchanged) and full
nodeid coverage (verified 5/5 intraday tests, 9/9 attribution tests enumerated). File:
`scripts/phase3_causal_gate.py`.

### 2. Bare-import module collision (collection blocker #3, masked until #1 fixed)

**Symptom:** `import file mismatch` for `test_phase4_v2_graph_persistence` across
`tests/` vs `research_tests/`.
**Root cause:** `tests/test_phase4_resolved_topology_identity.py:42` used a bare
`from test_phase4_v2_graph_persistence import _phase4_fixture` while its three siblings use
the package-qualified form — binding the bare name to the tests-side copy before research
collection.
**Fix:** one-line package qualification. (DP-class: sibling-convention drift.)

### 3. Native-state producer/consumer contract drift (collection blocker #1)

**Symptom:** `ImportError: cannot import name 'DeclaredNativeAdapter'` —
`test_foundation_research_projection_contracts.py` targets an earlier iteration of
`foundation_native_state_contract.py` (module registry + 3-arg `from_caller`) that the
current helper does not implement; reconciling means redesigning one side of an ACTIVE
capsule (`…native-state-contract-core`), which is not mine to invent.
**Fix (honest quarantine, not a fake-green):** conditional module-level `pytest.skip`
naming the missing symbols and the owning capsule; self-heals (runs again) the moment the
producer API lands. Extended the gate's skip contract
(`NATIVE_STATE_CONTRACT_SKIP_*` in `phase3_causal_gate.py`) with count-pinned evidence;
note module-level skips emit no `-vv` nodeid line, so the contract pins count + `-rs`
summary source, with reason bytes pinned by the module itself.

### 4. A-01 tail: two single-space trigger-text drifts (the actual foundation blocker)

**Symptom:** seeded genuine-0005 upgrade refused by 0010's validator:
`state is not an exact declared prefix: []`; 8 pre-existing migration tests red.
**Root cause:** `research_dataset_manifests_refuse_secret_key` had TWO sources of truth —
0007's literal vs `migrate._expected_triggers()` — differing by one space after `(` and
one before `))`. Candidate-boundary 0 therefore never matched.
**Fix:** aligned 0007's literal to the canonical bytes (`research/domain/migrations/
0007_phase4_dataset_provenance.py`). Note: Codex's dirty tree already carried most of the
A-01 response (`_restore_table_contracts`, per-stage validation); this session finished it.
**Permanent regression:** `research_tests/test_foundation_a01_migration_upgrade.py` —
seeded-0005 → head with marker + full canonical trigger inventory + legacy payload byte
preservation + per-stage declared-trigger subsets. **Mutation-proven:** re-introducing the
drift turns the suite red; restoring returns green.

### 5. Fixture import-order dependency (exposed during A-01 verification)

**Symptom:** `_make_populated_0007` failed on its own `DROP TABLE
research_ir_v2_graph_versions` — `create_all` ran before any module registered the model
tables (the runner imports `research.domain.models` only inside `migrate_research_db`).
**Fix:** test-only eager registration import at top of
`research_tests/test_ir_v2_research_migration.py`.

### 6. Remaining reds deliberately NOT touched (A-04 class)

Seven tests stay red — identical set pre- and post-change — all built on
`_make_populated_0007`/empty-current-schema hybrids that stamp pre-0010 markers onto
post-0010 constraint shapes. The audit itself ruled these fixtures invalid evidence.
Force-fixing them would require the historical-shape builder that belongs to the reserved
forward-replay capsule; faking it would be the exact false-green this repo exists to kill.
Disposition recorded in `09-migration-contract-decision.md`.

### 7. A-02 closed: booleans can no longer become executable market numbers

**New authoritative rule:** `app/market_data/numeric.py::market_float` — rejects bool
*before* coercion (bool ⊂ int is the whole defect), refuses non-numbers and non-finite
floats, returns plain float.
**Applied at every raw ingress**, each keeping its own failure vocabulary:
- `kite.candle_from_row` (extracted; OHLC previously passed through **uncoerced** — worse
  than coercion) → `ProviderReadError`
- `dhan.candle_from_columns_row` (extracted) → `ProviderReadError`
- `upstox._to_candle` (gated inside existing mapper) → `ProviderReadError`
- `replay.candle_from_record` (extracted; also fixed `or 0` swallowing `False` BEFORE the
  gate — caught by the regression suite itself) → `NumericIngressError`
- `dataset_store.encode_candles` (storage boundary double-check) → `DatasetStoreError`

**Regression:** `tests/test_market_numeric_ingress.py` — True/False injected into every
OHLCV field at every boundary + happy-path parity (naive-IST epoch, volume defaults,
roundtrip bytes). **Mutation-proven:** relaxing the rule turns 30+ tests red; restore →
green.

## Verification ledger

| Check | Command | Result |
|---|---|---|
| Collection restored | `.venv/bin/python -m pytest --collect-only tests research_tests` | `6010 tests collected`, 0 errors |
| A-02 regression | `pytest -q tests/test_market_numeric_ingress.py` | all green |
| A-02 mutation | relax `market_float` → run → restore | FAILED(30+) → green |
| A-01 regression | `pytest -q research_tests/test_foundation_a01_migration_upgrade.py` | all green |
| A-01 mutation | re-introduce space drift → run → restore | FAILED → green |
| Provider/dataset subsystems | kite/dhan/replay/dataset_store/provider_* suites | all green |
| Migration family | `research_tests/test_ir_v2_research_migration.py` | 7 red (A-04 hybrid-fixture class, pre-existing, documented) |
| Full-suite phase gate | `pytest -q tests research_tests` | see final log (running at doc time; result recorded below when complete) |

## Explicit nonclaims

Nothing here proves runtime execution, provider capability success, deployment readiness,
production capacity, or live/money authority. No live-order-path file was modified
(`kite_venue.py`, `venue.py`, `brokers.py` hashes still match their frozen values). Nothing
was committed, pushed, or deployed — commit remains owner-controlled per house rules.

---

# Round 2 — driving to Phase-5 readiness (same session, owner directive: "fix everything in the way")

### 8. Hybrid fixtures replaced by genuine forward-replay history (A-04 closure)

`_make_populated_0007` now builds the 0007 state by replaying the **production** 0006/0007
migrations over the genuine seeded-0005 fixture, then stamping the era marker — zero
hand-written historical DDL, exactly the audit's "exact projections, not rewound schemas"
prevention invariant. Five retired-head assertions (`"0008"`-era pins across
`test_ir_v2_research_migration.py` and `test_strategy_admissions.py`) refreshed to
`migrate.HEAD_VERSION` with intent-preserving comments; the genuine-0004 upgrade test now
rides to current head with legacy rows still unrewritten.

### 9. PRODUCT DEFECT: interrupted-0006 recovery refused its own sanctioned state

`_validate_schema`'s 0005-additive recovery swap compared the surviving DDL against
**current metadata** (post-0010 compound JSON constraints) while production's
`_upgrade_ir_v2_admissions` injects columns via the **frozen pre-0010 projection**. A real
crash between the ALTER and the marker advance would therefore fail restart validation
forever. Fixed: the swap now uses the frozen additive contract. Mutation-proven (revert →
test_failed_0006 red; restore → green).

### 10. PRODUCT DEFECT: the staged 0005 path never installed admission triggers

Fresh installs receive the admission `trg_*_no_update/no_delete` contract wholesale; the
genuine 0004→head staged path created the table with **no triggers**, failing the 0010
prefix validator. `_upgrade_strategy_admissions` now installs the complete contract from
`_expected_triggers()` (single canonical source), idempotently. Mutation-proven (block
disabled → red; restored → green).

### 11. Execution-plane retired-head test made head-relative

`test_0037_is_the_single_additive_execution_head…` pinned head `"0037"`; in-flight 0038/0039
exist. Refreshed to assert against `migrate.head_revision()` so the single-additive-head +
schema-matches-models contract survives future migrations. Execution migration suites: green.

### 12. Native-state contract helper: wire root-check rejected its own encoder

`strict_to_wire` demanded a `{"type": …}` root while `from_caller` digests tuple payloads
and the encoder emits five node shapes. Root check now mirrors `strict_from_wire`'s decoder
exactly. Separately, the test declaration carried an **empty sequences tuple**, making the
comparator's `sequence_bindings` mutation vacuous — a live DP-014 instance; the declaration
now carries a real `SequenceDeclaration` witness. `test_foundation_native_state_contract_core`
fully green.

### 13. PRODUCT SURFACE: `/api/readiness` rehomed behind authentication

The tenancy change made `/api/health` tenant-neutral (correct: execution state must not
cross an unauthenticated boundary) but orphaned the rich readiness payload — 10
baseline-allowlisted reds. New authenticated `GET /api/readiness` (+ `/api/v1/readiness`
mirror) serves the full payload with its historical semantics: `ok` tracks the verdict,
`build` always identifies itself, **503 when any check fails**, and a probe that raises
answers 503 naming itself (`failed_checks=["probe"]`) — a 500 here is indistinguishable
from a dead process to every monitor. Public `/api/health` keeps its neutral shape and its
two public-contract tests untouched. All 15 health/readiness tests green.

### 14. A-05 closed: marker shape declared as a dialect contract

SQLite `(version, schema_cookie)` vs PostgreSQL `(version)` documented at
`_VERSION_COLUMNS` (why the cookie exists; why PG has none) and pinned by
`test_marker_shape_is_a_declared_dialect_contract` in both directions.

## Round-2 verification ledger

| Check | Result |
|---|---|
| `research_tests/test_ir_v2_research_migration.py` + a01 + strategy_admissions + execution-migration files | green (PG-harness skips only) |
| `tests/test_health_endpoint.py` + `test_feed_quality_end_to_end.py` | 15/15 green (was 10 allowlisted reds) |
| `tests/test_foundation_native_state_contract_core.py` | 3/3 green |
| Mutation proofs | recovery-swap revert → red; 0005-install removal → red; both restored green |
| Full-suite phase gate | running at doc time — result recorded in the final handoff |

### 15. Round-2 gate results and smoke-script admission update

Full gate after all fixes: **5,909 passed / 73 failed / 100 skipped**. All 73 attributed to
pre-existing in-flight-capsule staleness (full table + owning capsules in
`11-gate-triage-and-readiness.md`); none caused by this session's edits beyond the two
causal-gate self-test pins fixed inline. `scripts/backtest_smoke.py` updated to the
Phase-3 admission contract (persists the canonical fixture receipt, names it at
`start_sweep`) → **SWEEP OK ✓ EXIT 0**; `dryrun.py 700` → **LEDGER OK ✓**.
