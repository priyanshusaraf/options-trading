"""Permit durable user ids in review creator envelopes.

Revision ID: 0029
Revises: 0028
"""
from __future__ import annotations

import sqlalchemy as sa
import hashlib
import json
from alembic import op


revision, down_revision = "0029", "0028"
branch_labels = depends_on = None


_TABLES = (
    ("project_review_notes", "ck_review_note_owner"),
    ("project_review_saved_views", "ck_review_view_owner"),
    ("project_review_snapshots", "ck_review_snapshot_owner"),
)
_USER_CHECK = "length(created_by) BETWEEN 1 AND 64"
_LEGACY_CHECK = "created_by = 'owner'"
_PROOF = "_review_0029_rebuild_proofs"


def _replace(check: str) -> None:
    # SQLite cannot alter a CHECK in place. Alembic's recreate path copies the
    # complete table transactionally, preserving historical `owner` bytes while
    # replacing only this envelope constraint.
    for table, name in _TABLES:
        _recover_recreate_temp(table)
        _prove_source(table)
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.drop_constraint(name, type_="check")
            batch.create_check_constraint(name, check)
        _verify_final_and_clear(table)
    # The snapshot immutability triggers are SQLite catalogue objects and must
    # be restored after its table recreation.
    for name, operation in (("project_review_snapshots_refuse_update", "UPDATE"),
                            ("project_review_snapshots_refuse_delete", "DELETE")):
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
        op.execute(
            f"CREATE TRIGGER {name} BEFORE {operation} ON project_review_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'review snapshots are immutable'); END")


def _recover_recreate_temp(table: str) -> None:
    """Resume an interrupted Alembic SQLite recreate without guessing payload.

    Before the source drop both tables exist, so the incomplete temporary copy
    is discarded.  After source drop the temporary table is the only copy; it
    is promoted back under the authoritative name and the normal recreation
    reruns.  No row is copied or synthesized by this recovery path.
    """
    temp = f"_alembic_tmp_{table}"
    names = set(sa.inspect(op.get_bind()).get_table_names())
    if table in names and temp in names:
        _verify(table, table)
        op.execute(f"DROP TABLE {temp}")
    elif table not in names and temp in names:
        _verify(table, temp)
        op.execute(f"ALTER TABLE {temp} RENAME TO {table}")


def _rows(table: str) -> tuple[int, str]:
    rows = op.get_bind().execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all()
    body = json.dumps([list(row) for row in rows], default=str, separators=(",", ":"))
    return len(rows), hashlib.sha256(body.encode()).hexdigest()


def _ensure_proofs() -> None:
    op.execute(sa.text(
        f"CREATE TABLE IF NOT EXISTS {_PROOF} (table_name VARCHAR(64) PRIMARY KEY, "
        "row_count INTEGER NOT NULL, row_digest VARCHAR(64) NOT NULL)"))


def _prove_source(table: str) -> None:
    _ensure_proofs()
    count, digest = _rows(table)
    existing = op.get_bind().execute(sa.text(
        f"SELECT row_count,row_digest FROM {_PROOF} WHERE table_name=:table"), {"table": table}
    ).one_or_none()
    if existing is None:
        op.get_bind().execute(sa.text(
            f"INSERT INTO {_PROOF} (table_name,row_count,row_digest) VALUES (:table,:count,:digest)"),
            {"table": table, "count": count, "digest": digest})
    elif tuple(existing) != (count, digest):
        raise RuntimeError(f"0029 recovery refused: source proof mismatch for {table}")


def _verify(table: str, actual_table: str) -> None:
    names = set(sa.inspect(op.get_bind()).get_table_names())
    if _PROOF not in names:
        raise RuntimeError(f"0029 recovery refused: unproven temporary table for {table}")
    proof = op.get_bind().execute(sa.text(
        f"SELECT row_count,row_digest FROM {_PROOF} WHERE table_name=:table"), {"table": table}
    ).one_or_none()
    if proof is None or tuple(proof) != _rows(actual_table):
        raise RuntimeError(f"0029 recovery refused: payload proof mismatch for {table}")


def _verify_final_and_clear(table: str) -> None:
    _verify(table, table)
    op.get_bind().execute(sa.text(f"DELETE FROM {_PROOF} WHERE table_name=:table"), {"table": table})
    if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {_PROOF}")).scalar_one() == 0:
        op.execute(sa.text(f"DROP TABLE {_PROOF}"))


def upgrade() -> None:
    _replace(_USER_CHECK)
    # 0028 leaves this proof table only when an interrupted creation was
    # subsequently recovered. A successful migration chain has no unfinished
    # session-table rebuild, so do not carry bookkeeping into the head schema.
    op.execute("DROP TABLE IF EXISTS _user_sessions_0028_creation_proofs")


def downgrade() -> None:
    _replace(_LEGACY_CHECK)
