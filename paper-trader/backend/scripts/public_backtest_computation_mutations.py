"""Mutation evidence for Task 4C's public-computation safety boundaries.

Run from ``backend`` with ``.venv/bin/python scripts/public_backtest_computation_mutations.py``.
Each mutant must make its focused guard fail; original bytes are restored after
every attempt, including a failing test runner.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTEST = [sys.executable, "-m", "pytest", "-q"]
MUTATIONS = (
    ("payload allowlist", ROOT / "app/backtest/public_computation.py",
     "if unknown:\n", "if False:\n",
     ["tests/test_public_backtest_computation.py::test_public_payload_is_a_versioned_exact_allowlist_and_never_copies_local_metadata"]),
    ("catalog authentication", ROOT / "app/backtest/public_computation.py",
     "and _module_source_digest(strategy) == item[\"source_digest\"])", "and True)",
     ["tests/test_public_backtest_computation.py::test_public_catalog_refuses_checked_in_strategy_when_its_source_digest_changes"]),
    ("address assertion", ROOT / "app/backtest/dataset_store.py",
     "if address is not None and address != recomputed_address:", "if False:",
     ["tests/test_dataset_store.py::test_put_recomputes_supplied_address_before_any_filesystem_write"]),
    ("idempotent prior artifact", ROOT / "app/backtest/dataset_store.py",
     "if existing is not None:", "if False:",
     ["tests/test_dataset_store.py::test_failed_idempotent_retry_never_deletes_prior_valid_artifact"]),
    ("parallel shared lookup", ROOT / "app/backtest/sweep.py",
     "        public = _public_reusable_values(prepared, strat, phash)\n        if public is not None:\n            _measure(\"cache_public_shared\", owner_id=owner_id)\n            slots.append((\"ready\", public))",
     "        public = None\n        if public is not None:\n            _measure(\"cache_public_shared\", owner_id=owner_id)\n            slots.append((\"ready\", public))",
     ["tests/test_public_backtest_computation.py::test_parallel_shared_hit_is_planned_in_parent_and_cold_worker_publishes"]),
    ("downgrade preflight", ROOT / "migrations/versions/20260812_0027_public_backtest_computations.py",
     ("if TABLE in _names() and op.get_bind().execute(\n            sa.text(f\"SELECT 1 FROM {TABLE} LIMIT 1\")).first():",
      "if op.get_bind().execute(sa.text(f\"SELECT 1 FROM {TABLE} LIMIT 1\")).first():"),
     ("if False:", "if False:"),
     ["tests/test_schema_migrations.py::test_revision_0027_nonempty_downgrade_preflight_performs_no_recovery_ddl"]),
)


def main() -> int:
    reddened = 0
    for name, path, old, new, tests in MUTATIONS:
        original = path.read_text()
        olds, news = ((old, new) if isinstance(old, tuple) else ((old,), (new,)))
        if any(original.count(item) != 1 for item in olds):
            raise RuntimeError(f"{name}: expected exactly one mutation target")
        try:
            mutated = original
            for old_item, new_item in zip(olds, news):
                mutated = mutated.replace(old_item, new_item)
            path.write_text(mutated)
            result = subprocess.run(PYTEST + tests, cwd=ROOT,
                                    env={**os.environ, "PYTHONPATH": str(ROOT)},
                                    text=True, capture_output=True)
            if result.returncode == 0:
                raise RuntimeError(f"{name}: guard stayed green (vacuous)")
            reddened += 1
            print(f"PASS {name}: guard reddened")
        finally:
            path.write_text(original)
    print(f"{reddened}/{len(MUTATIONS)} public-computation mutations reddened and restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
