# Task 11 report: execution attribution and legacy quarantine

## Status

Independent final review returned **SPEC PASS / QUALITY PASS**. Root independently retained
38 binding/attribution passes and the corrected null-GraphVersion fallback probe. The task is
ready for its scoped commit; protected inherited files remain outside the task.

## Implemented boundaries

- New runner entries re-load and verify the owner-local receipt at the final order
  boundary, and compute entry signals with the admitted IR runtime. Legacy runtime
  remains exit-only.
- Live and paper broker owning seams reject absent, forged, foreign, or stale receipt
  addresses. A post-submit fill is booked only from its exact persisted original
  intent, preventing a registry change from stranding an already-filled order.
- `NewExecutionIntent.admission_address` is required and validated. Positions and
  trades copy source attribution; late-fill recovery reloads the durable intent.
- Manual open is routed through current receipt verification.
- Backfill is dry-run-first and enumerates current consumer schema. It appends an
  immutable `StrategyAdmission`; immutable `GraphVersion` rows are never updated.
  `load_verified_admission` accepts a null legacy GraphVersion address only when its
  exact owner-local receipt independently matches immutable graph bytes and current
  registry. A conflicting non-null address refuses.
- Backtest run/result and shadow/paper rows without the historical manifests/research
  receipt stay quarantined. `trend_impulse_v3` is `LEGACY_UNADMITTED`; the only
  handwritten mapping is exact current `expanding_z_v4` code identity plus byte-identical
  shipped equivalent IR graph.

## Mutation-isolated evidence

- Final process-entry guard: published valid signal reaches the final guard exactly once;
  guard refusal leaves broker-open spy empty. Removing that local guard makes the spy fire.
- Direct LiveBroker forged hash: owning receipt guard is called once and no external submit
  occurs.
- Direct PaperBroker forged hash: owning receipt guard is called once and no position is
  booked.
- Post-submit stale-receipt probe: persisted original intent books copied receipt without
  re-running current-registry verification.
- Paper position/trade propagation, transient recovery forgery, and null lifecycle intent
  each have direct seam tests.

## Completed focused commands

- `pytest -q -rA tests/test_execution_binding.py` — 31 passed.
- `pytest -q -rA tests/test_execution_admission_attribution.py` — 7 passed.
- `pytest -q tests/test_strategy_admission_backfill.py -k 'not run_backfill and not
  real_expanding and not null_graph'` — 15 passed.
- `pytest -q tests/test_strategy_admission_backfill.py -k 'run_backfill or
  real_expanding or null_graph'` — completed successfully as a separate slow-path run
  under the command cap.
- Root-found fixture correction: `test_null_graph_version_uses_exact_appended_receipt_but_conflict_refuses`
  now supplies the full immutable GraphVersion byte/identity surface while varying only
  `admission_address`; its exact rerun completed successfully. This did not weaken the
  production loader.
- `pytest -q tests/test_live_entry_durability.py -x` — 15 passed.
- `pytest -q tests/test_session_entry_guard.py tests/test_execution_admission_attribution.py
  tests/test_strategy_admission_backfill.py` — 24 passed.
- `python -m py_compile` on changed execution/backfill modules and `git diff --check` — pass.
- `pytest -q` final-boundary mutation probes (runner final guard, direct Live forged
  receipt, direct Paper forged receipt, and stale-after-submit original-intent booking)
  — 4 passed.

## Protected inherited files

The approved inherited SHA-256 values remain unchanged for `kite_venue.py`, `venue.py`,
`brokers.py`, and `test_broker_registry.py`.
