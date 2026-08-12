"""Add durable, digest-only user sessions.

Revision ID: 0028
Revises: 0027
"""
from __future__ import annotations

import hashlib
import re
import sqlite3

import sqlalchemy as sa
from alembic import op


revision, down_revision = "0028", "0027"
branch_labels = depends_on = None

TABLE = "user_sessions"
TEMP = "user_sessions__0028"
PROOF = "_user_sessions_0028_creation_proofs"
DDL = """CREATE TABLE __TABLE__ (
 session_id VARCHAR(64) NOT NULL,
 token_digest VARCHAR(64) NOT NULL,
 user_id VARCHAR(64) NOT NULL,
 organization_id VARCHAR(64) NOT NULL,
 issued_at DATETIME NOT NULL,
 expires_at DATETIME NOT NULL,
 revoked_at DATETIME,
 PRIMARY KEY (session_id),
 CONSTRAINT ck_user_sessions_token_digest CHECK (length(token_digest) = 64 AND token_digest = lower(token_digest) AND token_digest NOT GLOB '*[^0-9a-f]*'),
 CONSTRAINT fk_user_sessions_active_membership FOREIGN KEY (organization_id, user_id) REFERENCES memberships (organization_id, user_id) ON DELETE RESTRICT,
 CONSTRAINT uq_user_sessions_token_digest UNIQUE (token_digest)
)"""
INDEX = ("ix_user_sessions_owner_active", "organization_id, user_id, revoked_at, expires_at")


def _names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _digest(rows) -> str:
    body = []
    for row in rows:
        name, sql = row.name or "", row.sql or ""
        name = re.sub(r"user_sessions(?:__0028)?", "__table__", name)
        sql = re.sub(r"user_sessions(?:__0028)?", "__table__", sql)
        name = name.removesuffix("__0028")
        sql = sql.replace("__0028", "")
        normalized = " ".join(sql.replace('"', '').replace('`', '').split()).lower()
        normalized = re.sub(r"\s*\(\s*", "(", normalized)
        normalized = re.sub(r"\s*\)", ")", normalized)
        normalized = re.sub(r"\s*,\s*", ",", normalized)
        body.append(f"{row.type}:{name}:" + normalized)
    return hashlib.sha256("\n".join(body).encode()).hexdigest()


def _schema(table: str) -> str:
    rows = op.get_bind().execute(sa.text(
        "SELECT type,name,sql FROM sqlite_master "
        "WHERE tbl_name=:name AND type IN ('table','index','trigger') ORDER BY type,name"),
        {"name": table}).all()
    return _digest(rows)


def _target_schema(*, temporary: bool) -> str:
    raw = sqlite3.connect(":memory:")
    try:
        table = TEMP if temporary else TABLE
        suffix = "__0028" if temporary else ""
        raw.execute(DDL.replace("__TABLE__", table))
        raw.execute(f"CREATE INDEX {INDEX[0]}{suffix} ON {table} ({INDEX[1]})")
        class Row:
            def __init__(self, value):
                self.type, self.name, self.sql = value
        rows = raw.execute(
            "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=? "
            "AND type IN ('table','index','trigger') ORDER BY type,name", (table,)).fetchall()
        return _digest([Row(row) for row in rows])
    finally:
        raw.close()


def _make_index(table: str, *, temporary: bool) -> None:
    suffix = "__0028" if temporary else ""
    op.execute(sa.text(f"CREATE INDEX {INDEX[0]}{suffix} ON {table} ({INDEX[1]})"))


def _proof(table: str) -> None:
    expected = _target_schema(temporary=table == TEMP)
    if _schema(table) != expected or op.get_bind().execute(
            sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
        raise RuntimeError("0028 target contract proof failed")
    op.execute(sa.text(
        f"CREATE TABLE IF NOT EXISTS {PROOF} "
        "(table_name TEXT PRIMARY KEY,row_count INTEGER NOT NULL,"
        "schema_digest TEXT NOT NULL,phase TEXT NOT NULL)"))
    op.get_bind().execute(sa.text(
        f"INSERT OR REPLACE INTO {PROOF} VALUES (:t,0,:s,'built')"),
        {"t": TABLE, "s": expected})


def _validate(table: str) -> None:
    row = op.get_bind().execute(sa.text(
        f"SELECT row_count,schema_digest,phase FROM {PROOF} WHERE table_name=:t"),
        {"t": TABLE}).one_or_none()
    actual = _schema(table)
    expected = _target_schema(temporary=table == TEMP)
    populated = op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first()
    if (row is None or row.row_count != 0 or row.phase != "built"
            or actual != row.schema_digest or row.schema_digest != expected or populated):
        raise RuntimeError("0028 refuses malformed completed user-session table")


def _promote_indexes() -> None:
    names = {row[0] for row in op.get_bind().execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=:t"), {"t": TABLE})}
    if f"{INDEX[0]}__0028" not in names:
        return
    op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX[0]}__0028"))
    _make_index(TABLE, temporary=False)


def _clear_proof() -> None:
    if PROOF not in _names():
        return
    op.get_bind().execute(sa.text(f"DELETE FROM {PROOF} WHERE table_name=:t"), {"t": TABLE})
    if not op.get_bind().execute(sa.text(f"SELECT 1 FROM {PROOF} LIMIT 1")).first():
        op.execute(sa.text(f"DROP TABLE {PROOF}"))


def finalize_after_stamp(bind) -> None:
    """Remove completion evidence only after Alembic recorded revision 0028.

    ``upgrade`` cannot delete its own proof before the version update: a crash
    in that gap would leave an empty target table indistinguishable from a
    forged one.  ``migrations/env.py`` invokes this after ``run_migrations`` has
    stamped the revision in the same transaction.
    """
    names = set(sa.inspect(bind).get_table_names())
    if PROOF not in names:
        return
    bind.execute(sa.text(f"DELETE FROM {PROOF} WHERE table_name=:t"), {"t": TABLE})
    if not bind.execute(sa.text(f"SELECT 1 FROM {PROOF} LIMIT 1")).first():
        bind.execute(sa.text(f"DROP TABLE {PROOF}"))


def _recover() -> None:
    names = _names()
    if TEMP in names:
        if TABLE not in names:
            if PROOF not in names:
                raise RuntimeError("0028 refuses unproven source-absent temporary user-session table")
            _validate(TEMP)
            op.execute(sa.text(f"ALTER TABLE {TEMP} RENAME TO {TABLE}"))
            _promote_indexes()
            _validate(TABLE)
        else:
            proof = PROOF in names and op.get_bind().execute(sa.text(
                f"SELECT 1 FROM {PROOF} WHERE table_name=:t"), {"t": TABLE}).first()
            if proof:
                _validate(TEMP)
            op.execute(sa.text(f"DROP TABLE {TEMP}"))
    if TABLE in _names() and PROOF in _names():
        if op.get_bind().execute(sa.text(
                f"SELECT 1 FROM {PROOF} WHERE table_name=:t"), {"t": TABLE}).first():
            _promote_indexes()
            _validate(TABLE)
        # Keep the proof through Alembic's stamp boundary. ``env.py`` performs
        # final cleanup only after version 0028 is durable.
        return
    if TABLE in _names() and PROOF not in _names():
        # At a pre-0028 revision, even an exact empty target could have been
        # forged.  A successful 0028 migration carries its proof until Alembic
        # records the revision, so there is no valid source-bound target here.
        raise RuntimeError("0028 refuses unproved existing user-session table")


def upgrade():
    _recover()
    if TABLE in _names():
        return
    # The new table has no source rows.  Still use a proof before promotion so a
    # stale/temp table can never become authentication authority by looking close
    # enough to the target DDL.
    op.execute(sa.text(DDL.replace("__TABLE__", TEMP)))
    _make_index(TEMP, temporary=True)
    _proof(TEMP)
    # SQLite rolls back the proof INSERT if a process dies before the following
    # rename, while already-created DDL can survive.  Make the proof durable
    # before that boundary so restart can authenticate the temp table.
    op.get_bind().connection.driver_connection.commit()
    op.execute(sa.text(f"ALTER TABLE {TEMP} RENAME TO {TABLE}"))
    _promote_indexes()
    _validate(TABLE)


def downgrade():
    # A populated session table is an active authentication authority.  Refuse
    # before recovery mutates any unfinished upgrade state.
    if TABLE in _names() and op.get_bind().execute(
            sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
        raise RuntimeError("0028 downgrade refuses to discard durable user sessions")
    # A successful upgrade cleaned its proof only after Alembic stamped 0028,
    # so normal downgrade sees the canonical target with no proof.  Incomplete
    # proof state still goes through recovery; an unproved/tampered target is
    # never discarded as a side effect of asking to move backwards.
    if PROOF in _names():
        _recover()
    if TABLE not in _names():
        return
    if _schema(TABLE) != _target_schema(temporary=False):
        raise RuntimeError("0028 downgrade refuses non-target user-session schema")
    if op.get_bind().execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
        raise RuntimeError("0028 downgrade refuses to discard durable user sessions")
    op.execute(sa.text(f"DROP TABLE {TABLE}"))
