"""Alembic environment for the execution database.

Two things here are deliberate and load-bearing:

1. **The connection is injected, never configured.** `app.db.migrate` puts the live
   connection in `config.attributes["connection"]`. This module refuses to invent
   one. A migration therefore cannot run against a database other than the one the
   calling process is bound to — which is what keeps a pytest run (throwaway file)
   and a production boot (the real ledger) from ever being confusable.

2. **`render_as_batch=True`.** SQLite cannot ALTER a column, drop a column on old
   versions, or add a constraint. Batch mode makes Alembic do the 12-step
   create-new-table / copy / drop / rename dance instead of failing. This is the
   single capability the old hand-maintained ADD COLUMN dict did not have, and the
   reason every schema change from Phase B onwards is expressible.
"""
from __future__ import annotations

from alembic import context

from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def _configure(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,          # SQLite ALTER support — see module docstring
        compare_type=True,
        compare_server_default=True,
    )


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is None:
        raise RuntimeError(
            "No connection supplied. Migrations are driven programmatically — run "
            "`python -m app.db.migrate` (or app.db.migrate.upgrade_to_head), not the "
            "bare `alembic` CLI, so the target database is always the one this "
            "process is bound to. See alembic.ini."
        )
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()
        # Revision 0028 keeps its source-bound creation proof through the
        # version-stamp boundary.  Clean it only after Alembic has recorded the
        # revision, so an empty target table cannot masquerade as a completed
        # authentication migration after an interruption.
        version = connection.execute(
            __import__("sqlalchemy").text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
        if version == "0028":
            from importlib.util import module_from_spec, spec_from_file_location
            from pathlib import Path
            path = Path(__file__).parent / "versions" / "20260812_0028_user_sessions.py"
            spec = spec_from_file_location("_revision_0028_finalize", path)
            assert spec and spec.loader
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            module.finalize_after_stamp(connection)


if context.is_offline_mode():
    raise RuntimeError("offline (--sql) migration is not supported for this project")
run_migrations_online()
