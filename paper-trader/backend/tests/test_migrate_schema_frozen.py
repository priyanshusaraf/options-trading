"""`_migrate_schema()` is frozen at Alembic revision 0001.

Without this test the old mechanism stays the path of least resistance: adding one
line to a dict is easier than writing a revision, so that is what would happen, and
the migration framework would quietly become decoration. The dict cannot express a
rename, a type change, a constraint or a rollback — every future schema change
needs a real revision.

If this test fails you added a column to the legacy dict. Move it to a new file in
`migrations/versions/` instead:

    .venv/bin/python -m app.db.migrate history     # see where you are
    # write migrations/versions/<date>_<rev>_<slug>.py with upgrade()/downgrade()

The counts below are the frozen inventory, not a style rule — they are what the
owner's live paper_trader.db needed to reach the baseline.
"""
from __future__ import annotations

import inspect
import re

from app.db import session as session_mod

# Table -> number of ADD COLUMN entries, as of revision 0001.
FROZEN_INVENTORY = {
    "capital_state": 2,
    "instrument_state": 6,
    "positions": 22,
    "trades": 11,
    "equity_snapshots": 2,
    "backtest_results": 36,
    "backtest_runs": 3,
}
FROZEN_TOTAL = 82


def _legacy_additions() -> dict[str, int]:
    """Parse the frozen dict out of the source. Reading the source rather than
    calling the function is deliberate: the dict is a local, and a test that had to
    execute `_migrate_schema()` would need a database and would then be testing
    ALTER behaviour rather than the freeze."""
    src = inspect.getsource(session_mod._migrate_schema)
    body = src.split("additions = {", 1)[1]
    counts: dict[str, int] = {}
    table = None
    for line in body.splitlines():
        stripped = line.strip()
        m = re.match(r'^"([a-z_]+)":\s*\[', stripped)
        if m:
            table = m.group(1)
            counts[table] = 0
            continue
        if table and stripped.startswith("("):
            counts[table] += 1
        if stripped == "}":
            break
    return counts


def test_legacy_migration_dict_is_frozen():
    found = _legacy_additions()
    assert found == FROZEN_INVENTORY, (
        "_migrate_schema() changed. It is FROZEN at Alembic revision 0001 — it can "
        "only ADD COLUMN, has no version and cannot be rolled back. Write an "
        "Alembic revision in migrations/versions/ instead.\n"
        f"expected {FROZEN_INVENTORY}\n     got {found}"
    )
    assert sum(found.values()) == FROZEN_TOTAL


def test_freeze_is_documented_where_someone_would_edit():
    """The guard is worthless if the person about to add a line does not see it."""
    doc = session_mod._migrate_schema.__doc__ or ""
    assert "FROZEN" in doc and "migrations/versions" in doc, (
        "_migrate_schema's docstring must say it is frozen and where changes go — "
        "that docstring is the only warning an editor gets before this test fires"
    )
