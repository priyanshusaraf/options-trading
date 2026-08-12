# Task 2 report — strategy-configuration ownership

## RED

Before production changes, the two-owner repository test failed with:

```text
TypeError: create_watchlist() got an unexpected keyword argument 'owner_id'
```

## Delivered slice

- Revision `0023` moves watchlists, memberships, lifecycle records, generated strategies,
  and runtime overrides to owner-local identities. It preserves global opaque watchlist IDs.
- Deployment watchlist references are validated by owner and stored by value; no USER-plane
  foreign key remains on the MONEY deployment table.
- Repository, deploy bridge, registry hydration, scoped/runtime configuration, runner binding,
  and generated-key resolution receive explicit owner context and fail closed for a missing or
  foreign generated key.
- The replay script now requires an explicit `--owner-id`; it does not silently use a legacy
  owner.
- No fixed tenant/user capacity was introduced. Owner-local lookups use indexed predicates and
  the runtime composition remains stateless.

## Migration proof/recovery evidence

`0023` proves both copied payload and the exact SQLite-visible target contract before a source
table is dropped. The durable proof carries a schema digest captured from the migration-local
target DDL; recovery checks it before promotion. Recovery preflights every source-absent temp
before any recovery DDL, discards source-present stale temps, and retries cleanly after final
proof cleanup but before Alembic stamps the revision.

The migration suite covers populated `0022` preservation, fresh-v-upgraded contract parity for
all six transformed tables, every-table completed recovery, payload corruption for every
transformation, malformed schema/proof rejection, pre-proof schema mutation, FK mode ON/OFF
success and injected failure, stale-temp recovery, all-temp preflight, and downgrade refusal.

## Verification

Passed:

```text
.venv/bin/python -m pytest -q tests/test_schema_migrations.py -k 'revision_0023' --tb=short
30 passed

.venv/bin/python -m pytest -q \
  tests/test_user_plane_tenant_isolation.py tests/test_watchlists.py \
  tests/test_watchlist_conflicts.py tests/test_strategy_archive.py \
  tests/test_deploy_bridge.py tests/test_scoped_config.py \
  tests/test_generated_registry.py tests/test_engine_binding.py \
  tests/test_runtime_config_schema.py tests/test_trader_controls.py \
  tests/test_intraday_controls.py tests/test_live_broker.py \
  tests/test_strategy_identity.py tests/test_runtime_sltp.py \
  tests/test_phase8_engine.py tests/test_overtrade_settings.py \
  tests/test_ir_shadow_isolation.py --tb=short
```

`compileall` passed for changed Python surfaces:

```text
.venv/bin/python -m compileall -q app migrations/versions/20260812_0023_user_strategy_config_ownership.py scripts/ir_shadow_replay.py
git diff --check
```

The broad `compileall app migrations scripts` command remains blocked by the pre-existing
unrelated `scripts/provider_conformance_mutations.py` error: its `from __future__ import
annotations` is not first. This task leaves that file untouched.

The four protected broker/provider files were not edited or staged by this task.

## Final-review hardening

The final review rejected several claims that the first gate did not prove. The follow-up
fixes add these enforced boundaries:

- Generated assignments, paper bindings, rollback targets, and shadow resolution carry the
  owner into strategy resolution. A missing or foreign `gen_*` key never enters the legacy
  default fallback.
- Generated keys use the canonical `gen_` namespace and their composition key must equal the
  persisted key. Hydration replaces an owner's registry partition atomically, so a corrupt or
  removed current row evicts executable bytes loaded from an older row.
- Watchlist ID lookup applies the owner predicate in SQL before ORM materialization. Composite
  membership and lifecycle foreign keys reject cross-owner links.
- Backtest sweep ownership is a required keyword-only argument. The REST principal, background
  thread, process payload, worker hydration, and worker resolution all preserve that owner.
  Metadata lists built-ins plus only the caller's generated partition.
- Restart recovery now recognizes the window after a temp table was renamed but before its
  proof row was deleted. It validates the promoted table's payload and schema against the
  durable proof before clearing it, and refuses post-rename tampering without changing the
  revision, payload, schema, or caller FK mode.

Additional verification passed:

```text
152 passed — execution binding, generated registry, paper authority, watchlists/conflicts,
             deploy bridge, USER-plane isolation, multi-strategy backtests
42 passed  — revision 0023, parallel sweeps, pinned worker reads, pinned sweeps
95 passed  — remaining affected backtest/API suites
12 passed  — restored critical tests after mutation checks
```

Six deliberate mutations were killed: generated fallback, stale generated registry retention,
owner predicate removal from guessed watchlist lookup, promoted-proof validation removal,
portfolio owner replacement with a constant, and worker owner replacement with a constant.
An AST audit found no `start_sweep` call without `owner_id`. Focused `py_compile` and
`git diff --check` passed.
