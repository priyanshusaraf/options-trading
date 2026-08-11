# Task 1A.3 fix round 1 report

Starting commit: `4346d43`.

## Root cause and correction

The first retry pass exposed two independent durable SQLite faults.

- A completed 0021 downgrade table can have already become the 0020 source before Alembic writes
  the revision. The old refusal guard queried `owner_id` before recognizing that source shape,
  so retry crashed with `no such column: owner_id`.
- Paper and shadow provenance rebuilds copied indexes only from the live source. A crash after
  rename left the rebuilt table without indexes; retry saw that the obsolete graph foreign key was
  already absent and returned. This removed the partial active-authority unique indexes.

Revision 0021 now recovers every custom rebuild table before source-column checks or downgrade
refusal, makes refusal guards shape-aware, and carries a migration-local 0020 MONEY index
manifest. The manifest restores only missing named indexes, preserving the historical SQL and
partial predicates. The graph identifier collision guard runs before the generic non-legacy owner
guard, so the actual identity-collapse reason is reported before any DDL.

The fresh-v-upgraded comparator also found real MONEY column-order and broker-account FK-name
drift. `IrPaperDeployment` and `IrShadowDeployment` now declare the historical physical order and
the historical named account FK, without changing their fields or authority behavior.

## TDD evidence

Observed RED with the verified interpreter:

```text
pytest -q tests/test_schema_migrations.py -k \
  'revision_0021_downgrade_post_rename_retry_recovers_before_owner_refusal or \
   revision_0021_upgrade_money_post_rename_retry_restores_full_contract' --tb=short
```

Six fault nodes failed before production correction:

- downgrade post-rename retry for `graph_versions`, `ir_graph_layouts`,
  `ir_paper_deployments`, and `ir_shadow_deployments` failed in `_downgrade_refusal` with
  `OperationalError: no such column: owner_id`;
- upgrade post-rename retry for paper and shadow converged to head but had zero named indexes,
  instead of the full historical index set including the partial authority unique index.

The full-contract comparator then REDed on the migration/fresh mismatch for the named composite
graph FK, then on the actual MONEY column order and broker-account FK-name differences. The
two-owner same-identifier downgrade node REDed with the generic non-legacy owner error before the
specific graph collision guard was moved ahead of it.

New fault coverage contains 33 independently parameterized recovery nodes: source plus stale temp
and source-absent completed temp for all 11 custom 0021 rebuild tables (22 nodes), plus 11
downgrade post-rename retries. It asserts revision convergence, no remaining `__0021` table, and
ordered column/constraint/FK/index/trigger contract preservation. Paper and shadow post-rename
tests also compare named index SQL, including their partial unique predicates.

## Verification

All commands used:

```text
/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python
```

Completed gates:

```text
pytest -q tests/test_schema_migrations.py --tb=short                         # 87 passed
pytest -q [tenant, graph, layout, IR, paper, shadow, execution suites]       # 323 passed
python -m compileall -q app migrations tests                                  # exit 0
git diff --check                                                              # exit 0
```

The complete 0021 fresh-v-upgraded comparator passed for all affected tables:
`projects`, graph artifacts/versions, all six layout/archive tables, and paper/shadow deployments.
It compares column order/type/nullability/defaults, PK/unique/check constraints, parsed named FKs
and delete actions, named index SQL and triggers. The broad application gate emitted only the
existing Starlette/httpx deprecation warning.

Protected files remain unstaged and untouched:
`app/engine/kite_venue.py`, `app/engine/venue.py`, `app/providers/brokers.py`, and
`tests/test_broker_registry.py`.
