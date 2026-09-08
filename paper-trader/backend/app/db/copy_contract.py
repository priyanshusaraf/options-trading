"""Fail-closed, offline copy contract for the three database planes."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import sqlalchemy as sa
from sqlalchemy import Engine, MetaData, Table, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.sql.sqltypes import Boolean, Date, DateTime, Float, LargeBinary

from app.db.migrate import validate_paper_entry_lifecycle_manifest

TOOL_VERSION = "1"


class CopyRefusal(RuntimeError):
    """The copy cannot prove that its result is safe for cutover."""


@dataclass(frozen=True)
class CopyPlane:
    name: str
    source_path: Path
    destination_url: str
    metadata: MetaData
    marker_table: str | None
    source_head: str
    initialize_destination: Callable[[Engine], None]
    validate_destination: Callable[[Engine], None]
    destination_head: str | None = None


def _redacted_source(path: Path) -> str:
    return f"sqlite:{hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]}"


def _redacted_destination(url: str) -> str:
    parsed = make_url(url)
    authority = f"{parsed.get_backend_name()}://{parsed.host or 'local'}:{parsed.port or 5432}/{parsed.database or ''}"
    try:
        from research.guards import _search_path
        schema = ",".join(_search_path(url) or ()) or "unspecified"
    except Exception:
        schema = "unparseable"
    safe_identity = f"{authority}/schema:{schema}"
    return f"{authority}/schema:{schema}#{hashlib.sha256(safe_identity.encode()).hexdigest()[:12]}"


def _source_engine(path: Path) -> Engine:
    resolved = path.resolve()
    uri = f"file:{resolved}?mode=ro"

    def connect() -> sqlite3.Connection:
        connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    return sa.create_engine("sqlite://", creator=connect, future=True)


def _file_snapshot(path: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    # The shared-memory index is reader-owned coordination state; its mtime can
    # change merely because this read-only process opens a snapshot.
    for suffix in ("", "-wal"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            stat = candidate.stat()
            result[suffix or "db"] = [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]
    return result


def _validate_source_schema(plane: CopyPlane, engine: Engine) -> str:
    actual = set(inspect(engine).get_table_names())
    expected = set(plane.metadata.tables)
    if plane.marker_table:
        expected.add(plane.marker_table)
    if actual != expected:
        raise CopyRefusal(
            f"{plane.name} SQLite table inventory mismatch: "
            f"missing={sorted(expected-actual)} extra={sorted(actual-expected)}"
        )
    with engine.connect() as connection:
        if plane.name == "execution":
            rows = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            if rows != [plane.source_head]:
                raise CopyRefusal(f"unsupported execution SQLite schema head {rows!r}")
            if plane.source_head in {"0045", "0046", "0047", "0048"}:
                try:
                    validate_paper_entry_lifecycle_manifest(
                        connection, compatible_heads=frozenset({plane.source_head}))
                except RuntimeError as exc:
                    raise CopyRefusal(
                        "execution SQLite Paper lifecycle manifest is invalid") from exc
        elif plane.name == "research":
            rows = connection.execute(text(
                "SELECT version, schema_cookie FROM research_schema_version"
            )).all()
            cookie = int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one())
            if len(rows) != 1 or rows[0][0] != plane.source_head or int(rows[0][1]) != cookie:
                raise CopyRefusal("unsupported or stale research SQLite schema head")
        elif plane.name == "ledger":
            if plane.marker_table is not None:
                raise CopyRefusal("ledger SQLite must not carry a PostgreSQL version marker")
        else:
            raise CopyRefusal(f"unsupported plane {plane.name!r}")
        fk = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
        if fk != 1 or violations:
            raise CopyRefusal(f"{plane.name} SQLite foreign-key contract is invalid")
    _validate_sqlite_checks(engine, plane.metadata)
    # Reuse the current structural authority, with the exact-table check above closing its
    # intentional subset behavior. It is read-only reflection and performs no migration.
    try:
        if plane.name == "research":
            from research.domain.migrate import _validate_schema
            with engine.connect() as connection:
                _validate_schema(connection)
        elif plane.name == "execution":
            from app.db.migrate import _validate_current_schema
            _validate_current_schema(engine, plane.metadata.tables)
        else:
            _validate_sqlite_relational(engine, plane.metadata)
    except Exception as exc:
        raise CopyRefusal(f"{plane.name} SQLite current-schema validation failed") from exc
    return plane.source_head


def _normalise_sql(value: object) -> str:
    value = "".join(str(value).lower().replace('"', "").replace("`", "").split())
    while value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    return value


def _validate_sqlite_checks(engine: Engine, metadata: MetaData) -> None:
    inspector = inspect(engine)
    for table in metadata.sorted_tables:
        expected = {
            constraint.name: _normalise_sql(constraint.sqltext.compile(dialect=engine.dialect))
            for constraint in table.constraints
            if isinstance(constraint, sa.CheckConstraint) and constraint.name
        }
        actual = {
            constraint["name"]: _normalise_sql(constraint["sqltext"])
            for constraint in inspector.get_check_constraints(table.name)
            if constraint.get("name")
        }
        if expected != actual:
            raise CopyRefusal(f"{table.name} SQLite CHECK contract drift")


def _validate_sqlite_relational(engine: Engine, metadata: MetaData) -> None:
    """Exact read-only reflection for the markerless ledger SQLite authority."""
    inspector = inspect(engine)
    for table in metadata.sorted_tables:
        reflected = {column["name"]: column for column in inspector.get_columns(table.name)}
        if set(reflected) != set(table.c.keys()):
            raise CopyRefusal(f"{table.name} SQLite column-set drift")
        for column in table.columns:
            actual = reflected[column.name]
            if (not column.type._compare_type_affinity(actual["type"])
                    or bool(column.nullable) != bool(actual["nullable"])):
                raise CopyRefusal(f"{table.name}.{column.name} SQLite column contract drift")
        expected_pk = tuple(column.name for column in table.primary_key.columns)
        actual_pk = tuple(inspector.get_pk_constraint(table.name).get("constrained_columns") or ())
        if expected_pk != actual_pk:
            raise CopyRefusal(f"{table.name} SQLite primary-key drift")
        expected_unique = {tuple(column.name for column in constraint.columns)
                           for constraint in table.constraints
                           if isinstance(constraint, sa.UniqueConstraint)}
        actual_unique = {tuple(item["column_names"])
                         for item in inspector.get_unique_constraints(table.name)}
        if expected_unique != actual_unique:
            raise CopyRefusal(f"{table.name} SQLite unique-constraint drift")
        expected_indexes = {(tuple(index.columns.keys()), bool(index.unique))
                            for index in table.indexes}
        actual_indexes = {(tuple(index["column_names"]), bool(index.get("unique")))
                          for index in inspector.get_indexes(table.name)}
        if expected_indexes != actual_indexes:
            raise CopyRefusal(f"{table.name} SQLite index drift")
        expected_fks = {(tuple(fk.column_keys), fk.referred_table.name,
                         tuple(element.column.name for element in fk.elements))
                        for fk in table.foreign_key_constraints}
        actual_fks = {(tuple(fk["constrained_columns"]), fk["referred_table"],
                       tuple(fk["referred_columns"]))
                      for fk in inspector.get_foreign_keys(table.name)}
        if expected_fks != actual_fks:
            raise CopyRefusal(f"{table.name} SQLite foreign-key drift")


def _typed_value(column, value) -> bytes:
    if value is None:
        return b"n"
    typ = column.type
    if isinstance(typ, Boolean):
        if value not in (0, 1, False, True):
            raise CopyRefusal(f"loose SQLite Boolean in {column.table.name}.{column.name}")
        return b"b1" if bool(value) else b"b0"
    if isinstance(typ, LargeBinary):
        if not isinstance(value, bytes):
            raise CopyRefusal(f"loose SQLite binary in {column.table.name}.{column.name}")
        return b"x" + len(value).to_bytes(8, "big") + value
    if isinstance(typ, Float):
        if not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(float(value)):
            raise CopyRefusal(f"invalid float in {column.table.name}.{column.name}")
        return b"f" + float(value).hex().encode()
    if isinstance(typ, (DateTime, Date)):
        if isinstance(value, str):
            try:
                value = dt.datetime.fromisoformat(value) if isinstance(typ, DateTime) else dt.date.fromisoformat(value)
            except ValueError as exc:
                raise CopyRefusal(f"invalid temporal value in {column.table.name}.{column.name}") from exc
        if isinstance(value, dt.datetime) and value.tzinfo is not None:
            raise CopyRefusal(f"timezone-bearing value in naive column {column.table.name}.{column.name}")
        if not isinstance(value, (dt.date, dt.datetime)):
            raise CopyRefusal(f"loose SQLite temporal value in {column.table.name}.{column.name}")
        if isinstance(typ, DateTime):
            if not isinstance(value, dt.datetime):
                raise CopyRefusal(f"loose SQLite datetime in {column.table.name}.{column.name}")
            return b"t" + value.isoformat(timespec="microseconds").encode()
        if isinstance(value, dt.datetime) or not isinstance(value, dt.date):
            raise CopyRefusal(f"loose SQLite date in {column.table.name}.{column.name}")
        return b"d" + value.isoformat().encode()
    if isinstance(value, bool):
        return b"b1" if value else b"b0"
    if isinstance(value, int):
        return b"i" + str(value).encode()
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return b"s" + len(raw).to_bytes(8, "big") + raw
    raise CopyRefusal(f"unsupported value type in {column.table.name}.{column.name}")


def _coerce_for_destination(column, value):
    if value is None:
        return None
    if isinstance(column.type, Boolean):
        return bool(value)
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return dt.datetime.fromisoformat(value)
    if isinstance(column.type, Date) and not isinstance(column.type, DateTime) and isinstance(value, str):
        return dt.date.fromisoformat(value)
    return value


def _row_digest(table: Table, row: dict[str, object]) -> str:
    digest = hashlib.sha256()
    for column in table.columns:
        digest.update(column.name.encode() + b"\0")
        digest.update(_typed_value(column, row[column.name]) + b"\0")
    return digest.hexdigest()


def _stream_summary(connection, table: Table, *, batch_size: int,
                    destination=None) -> dict[str, object]:
    order = list(table.primary_key.columns)
    statement = sa.select(table).order_by(*order) if order else sa.select(table)
    result = connection.execution_options(stream_results=True).execute(statement)
    table_digest = hashlib.sha256()
    pk_digest = hashlib.sha256()
    partitions: dict[str, dict[str, int]] = {}
    count = 0
    while True:
        batch = [dict(row._mapping) for row in result.fetchmany(batch_size)]
        if not batch:
            break
        _source_batch_read(table, count, batch)
        if destination is not None:
            payload = [{column.name: _coerce_for_destination(column, row[column.name])
                        for column in table.columns} for row in batch]
            destination.execute(table.insert(), payload)
        for row in batch:
            digest = bytes.fromhex(_row_digest(table, row))
            table_digest.update(digest)
            pk_digest.update(b"\0".join(
                _typed_value(column, row[column.name]) for column in table.primary_key.columns
            ) + b"\n")
            for dimension in ("owner_id", "broker_account_id"):
                if dimension in row:
                    key = hashlib.sha256(str(row[dimension]).encode()).hexdigest()[:16]
                    values = partitions.setdefault(dimension, {})
                    values[key] = values.get(key, 0) + 1
            count += 1
    return {"rows": count, "pk_digest": pk_digest.hexdigest(),
            "row_digest": table_digest.hexdigest(), "partition_counts": partitions}


def _source_batch_read(_table: Table, _offset: int, _rows: list[dict[str, object]]) -> None:
    """Test seam for a concurrent source commit after snapshot acquisition."""


def _validate_semantic_ownership(connection, metadata: MetaData) -> None:
    if "broker_accounts" not in metadata.tables:
        return
    accounts = {
        row.broker_account_id: row.owner_id
        for row in connection.execute(sa.select(
            metadata.tables["broker_accounts"].c.broker_account_id,
            metadata.tables["broker_accounts"].c.owner_id,
        ))
    }
    for table in metadata.tables.values():
        names = set(table.c.keys())
        if "broker_account_id" not in names or table.name == "broker_accounts":
            continue
        selected = [table.c.broker_account_id]
        selected.extend(table.c[name] for name in ("owner_id", "classification", "scope_key")
                        if name in names)
        for row in connection.execute(sa.select(*selected)).mappings():
            account = row["broker_account_id"]
            owner = row.get("owner_id")
            if account is None:
                explicitly_owner_scoped = (
                    table.name == "execution_outbox_event"
                    and owner is not None
                    and row.get("classification") == "private"
                    and row.get("scope_key") == f"private:{owner}:*"
                )
                if explicitly_owner_scoped:
                    continue
                raise CopyRefusal(f"{table.name} violates broker-account ownership")
            if account not in accounts or ("owner_id" in names and owner != accounts[account]):
                raise CopyRefusal(f"{table.name} violates broker-account ownership")

    # A scalar FK can preserve row existence while crossing a tenant boundary. For
    # every metadata FK, require all shared scope columns to agree with the referenced
    # row even when the historical database constraint names only the local identifier.
    scope_columns = {
        "owner_id", "organization_id", "user_id", "broker_account_id",
        "broker", "deployment_id", "project_id", "graph_identifier",
        "operation_id", "run_id",
    }
    for table in metadata.sorted_tables:
        for foreign_key in table.foreign_key_constraints:
            target = foreign_key.referred_table
            local_fk_names = {element.parent.name for element in foreign_key.elements}
            shared = (set(table.c.keys()) & set(target.c.keys()) & scope_columns) - local_fk_names
            if not shared:
                continue
            if target is table:
                # Self-referential chain (e.g. authority rows superseding prior
                # authority): joining a table to itself renders ONE name twice,
                # which SQLite refuses as ambiguous. Alias the referred side.
                target_side = table.alias(f"{table.name}__scope_check")
                joined = sa.and_(*(
                    table.c[element.parent.name] == target_side.c[element.column.name]
                    for element in foreign_key.elements
                ))
                mismatched = sa.or_(*(
                    table.c[name] != target_side.c[name] for name in sorted(shared)))
            else:
                joined = sa.and_(*(
                    element.parent == element.column for element in foreign_key.elements
                ))
                mismatched = sa.or_(*(table.c[name] != target.c[name] for name in sorted(shared)))
            statement = (sa.select(sa.literal(1)).select_from(table.join(target_side if target is table else target, joined))
                         .where(mismatched).limit(1))
            if connection.execute(statement).first() is not None:
                raise CopyRefusal(
                    f"{table.name} violates {target.name} semantic scope"
                )

    # These links are intentionally by value rather than physical FKs. Keep the
    # relation inventory explicit so a new row shape cannot silently broaden it.
    virtual_relations = (
        ("execution_intents", "broker_accounts", (
            ("owner_id", "owner_id"), ("broker_account_id", "broker_account_id"),
            ("broker", "broker"), ("account_scope", "external_account_id"),
        ), None),
        ("execution_intents", "broker_connections", (
            ("owner_id", "owner_id"), ("broker_account_id", "broker_account_id"),
            ("broker", "broker"), ("connection_scope", "scope"),
        ), None),
        ("oauth_callback_states", "broker_connections", (
            ("connection_id", "id"), ("organization_id", "owner_id"),
        ), None),
        ("deployments", "watchlists", (
            ("watchlist_id", "id"), ("owner_id", "owner_id"),
        ), "watchlist_id"),
        ("strategy_lifecycle", "watchlists", (
            ("deployed_watchlist_id", "id"), ("owner_id", "owner_id"),
        ), "deployed_watchlist_id"),
        ("ir_paper_deployments", "graph_versions", (
            ("owner_id", "owner_id"), ("graph_identifier", "graph_identifier"),
            ("graph_version", "version"),
            ("graph_content_address", "content_address"),
        ), None),
        ("ir_shadow_deployments", "graph_versions", (
            ("owner_id", "owner_id"), ("graph_identifier", "graph_identifier"),
            ("graph_version", "version"),
            ("graph_content_address", "content_address"),
        ), None),
    )
    for child_name, parent_name, pairs, optional_column in virtual_relations:
        if child_name not in metadata.tables or parent_name not in metadata.tables:
            continue
        child, parent = metadata.tables[child_name], metadata.tables[parent_name]
        match = sa.and_(*(child.c[left] == parent.c[right] for left, right in pairs))
        predicate = ~sa.exists(sa.select(sa.literal(1)).select_from(parent).where(match))
        if child_name == "execution_intents" and parent_name == "broker_connections":
            # A Paper entry intent is durable lifecycle identity, not a fabricated
            # external connection or broker acknowledgement. Its exact canonical
            # marker is the only supported exception to the real-connection link.
            paper_identity = sa.and_(
                child.c.connection_scope == "paper",
                child.c.context_json == '{"schema":"paper-entry-lifecycle/1"}',
            )
            predicate = sa.and_(sa.not_(paper_identity), predicate)
        if optional_column is not None:
            predicate = sa.and_(child.c[optional_column].is_not(None), predicate)
        missing = (sa.select(sa.literal(1)).select_from(child)
                   .where(predicate)
                   .limit(1))
        if connection.execute(missing).first() is not None:
            raise CopyRefusal(f"{child_name} violates {parent_name} semantic link")

    if {"user_sessions", "memberships"} <= set(metadata.tables):
        sessions = metadata.tables["user_sessions"]
        memberships = metadata.tables["memberships"]
        invalid_active_session = (sa.select(sa.literal(1)).select_from(
            sessions.join(memberships, sa.and_(
                sessions.c.organization_id == memberships.c.organization_id,
                sessions.c.user_id == memberships.c.user_id,
            ))).where(
                sessions.c.revoked_at.is_(None), memberships.c.status != "active"
            ).limit(1))
        if connection.execute(invalid_active_session).first() is not None:
            raise CopyRefusal("active user_sessions require an active membership")

    if 'browser_credentials' in metadata.tables:
        from app.accounts.browser_auth import valid_verifier
        credentials = metadata.tables['browser_credentials']
        for row in connection.execution_options(stream_results=True).execute(sa.select(credentials.c.verifier)).yield_per(200):
            if not valid_verifier(row.verifier):
                raise CopyRefusal('browser credential profile is unsupported')
    if {'browser_sessions', 'user_sessions'} <= set(metadata.tables):
        browser = metadata.tables['browser_sessions']
        sessions = metadata.tables['user_sessions']
        rows = connection.execution_options(stream_results=True).execute(sa.select(
            sessions.c.user_id, sessions.c.issued_at, sessions.c.expires_at,
            browser.c.last_seen_at).select_from(browser.join(sessions))).yield_per(200)
        for row in rows:
            if (row.user_id == 'owner-user' or row.expires_at <= row.issued_at
                    or row.expires_at - row.issued_at > dt.timedelta(hours=12)
                    or row.last_seen_at < row.issued_at or row.last_seen_at > row.expires_at):
                raise CopyRefusal('browser session lifetime or identity is invalid')
    if 'browser_auth_attempts' in metadata.tables:
        from app.accounts.browser_auth import MAX_COUNTERS, WINDOW_SECONDS, _now
        attempts = metadata.tables['browser_auth_attempts']
        retained = connection.scalar(sa.select(sa.func.count()).select_from(attempts))
        if retained > MAX_COUNTERS:
            raise CopyRefusal('browser attempt counter capacity is invalid')
        impossible = connection.execute(sa.select(attempts.c.key_digest).where(
            attempts.c.expires_at > _now() + dt.timedelta(seconds=WINDOW_SECONDS)).limit(1)).first()
        if impossible is not None:
            raise CopyRefusal('browser attempt window expiry is impossible')


def _hashed_identity(values: tuple[object, ...]) -> bytes:
    digest = hashlib.sha256()
    for value in values:
        encoded = str(value).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big") + encoded)
    return digest.digest()


def _streamed_identity_set(connection, table: Table, columns: tuple[str, ...],
                           *, batch_size: int = 500) -> set[bytes]:
    statement = sa.select(*(table.c[name] for name in columns)).distinct()
    result = connection.execution_options(stream_results=True).execute(statement)
    identities: set[bytes] = set()
    while True:
        rows = result.fetchmany(batch_size)
        if not rows:
            return identities
        identities.update(_hashed_identity(tuple(row)) for row in rows)


def _validate_cross_plane_semantics(planes: Iterable[CopyPlane]) -> None:
    by_name = {plane.name: plane for plane in planes}
    if not {"execution", "research", "ledger"} <= set(by_name):
        return
    engines = {
        name: sa.create_engine(by_name[name].destination_url, future=True, pool_pre_ping=True)
        for name in ("execution", "research", "ledger")
    }
    try:
        with (engines["execution"].connect() as execution,
              engines["research"].connect() as research,
              engines["ledger"].connect() as ledger):
            execution_accounts = _streamed_identity_set(
                execution, by_name["execution"].metadata.tables["broker_accounts"],
                ("owner_id", "broker_account_id"),
            )
            for table in by_name["ledger"].metadata.sorted_tables:
                names = set(table.c.keys())
                if not {"owner_id", "broker_account_id"} <= names:
                    continue
                ledger_pairs = _streamed_identity_set(
                    ledger, table, ("owner_id", "broker_account_id"),
                )
                if not ledger_pairs <= execution_accounts:
                    raise CopyRefusal(
                        f"ledger {table.name} owner/account has no execution broker account"
                    )

            execution_owners = _streamed_identity_set(
                execution, by_name["execution"].metadata.tables["organizations"],
                ("organization_id",),
            )
            for table in by_name["research"].metadata.sorted_tables:
                if "owner_id" not in table.c:
                    continue
                research_owners = _streamed_identity_set(research, table, ("owner_id",))
                if not research_owners <= execution_owners:
                    raise CopyRefusal(
                        f"research owner in {table.name} has no execution organization"
                    )
    finally:
        for engine in engines.values():
            engine.dispose()


def _validate_postgresql_constraints(connection) -> None:
    invalid = connection.execute(text("""
        SELECT conrelid::regclass::text, conname
        FROM pg_constraint
        WHERE connamespace = current_schema()::regnamespace AND NOT convalidated
        ORDER BY 1, 2
    """)).all()
    if invalid:
        raise CopyRefusal("PostgreSQL contains unvalidated relational constraints")


def _repair_sequences(connection, metadata: MetaData) -> list[dict[str, object]]:
    results = []
    for table in metadata.sorted_tables:
        for column in table.primary_key.columns:
            if not isinstance(column.type, sa.Integer) or len(table.primary_key.columns) != 1:
                continue
            sequence = connection.execute(text(
                "SELECT pg_get_serial_sequence(:table, :column)"
            ), {"table": table.name, "column": column.name}).scalar_one_or_none()
            if not sequence:
                continue
            maximum = connection.execute(sa.select(sa.func.max(column))).scalar_one()
            if maximum is None:
                connection.execute(text("SELECT setval(CAST(:sequence AS regclass), 1, false)"), {"sequence": sequence})
                next_value = 1
            else:
                connection.execute(text("SELECT setval(CAST(:sequence AS regclass), :maximum, true)"),
                                   {"sequence": sequence, "maximum": maximum})
                next_value = int(maximum) + 1
            results.append({"table": table.name, "column": column.name,
                            "copied_max": maximum, "next_at_least": next_value})
    return results


def _validate_credentials(connection, metadata: MetaData) -> None:
    if "broker_connections" not in metadata.tables:
        return
    table = metadata.tables["broker_connections"]
    pairs = connection.execute(sa.select(table.c.credential_ciphertext, table.c.credential_key_id)).all()
    encrypted = [pair for pair in pairs if pair[0] is not None or pair[1] is not None]
    if any(not ciphertext or not key_id for ciphertext, key_id in encrypted):
        raise CopyRefusal("broker credential ciphertext/key-id pairing is invalid")
    if encrypted:
        from app.core.credential_vault import key_id
        try:
            configured = key_id()
        except Exception as exc:
            raise CopyRefusal("PT_CREDENTIAL_KEY readiness is required for encrypted credentials") from exc
        if any(stored != configured for _ciphertext, stored in encrypted):
            raise CopyRefusal("configured credential key does not match copied encrypted credentials")


def _validate_content_addresses(connection, metadata: MetaData) -> None:
    if "ir_v2_editor_presentations" in metadata.tables:
        import json as _json
        from app.ir.hashing import canonical_json

        table = metadata.tables["ir_v2_editor_presentations"]
        required = {"schema", "positions", "groups", "viewport", "selection"}
        for encoded, format_version in connection.execute(sa.select(
                table.c.presentation_json, table.c.format_version)):
            try:
                document = _json.loads(encoded)
                valid = (
                    format_version == 2
                    and isinstance(document, dict)
                    and set(document) == required
                    and document.get("schema") == "strategy-os-v2-presentation/1"
                    and canonical_json(document) == encoded
                    and isinstance(document.get("positions"), dict)
                    and isinstance(document.get("groups"), dict)
                    and isinstance(document.get("selection"), dict)
                    and set(document["selection"]) == {"nodes", "edges", "outputs"}
                )
            except Exception:
                valid = False
            if not valid:
                raise CopyRefusal("v2 editor presentation is not canonical closed JSON")
    if "chart_context_annotations" in metadata.tables:
        from app.chart.annotation_geometry import decode_applicability, decode_geometry
        from app.chart.annotation_repository import (
            AnnotationLimit, validate_annotation_group_ceiling,
        )

        table = metadata.tables["chart_context_annotations"]
        try:
            validate_annotation_group_ceiling(connection, table)
        except AnnotationLimit as exc:
            raise CopyRefusal(
                "chart annotation group exceeds the presentation ceiling") from exc
        rows = connection.execution_options(stream_results=True).execute(sa.select(
            table.c.geometry_json, table.c.geometry_address,
            table.c.applicability_json, table.c.applicability_address,
        )).yield_per(200)
        for geometry_json, geometry_address, applicability_json, applicability_address in rows:
            try:
                geometry = decode_geometry(geometry_json)
                applicability = decode_applicability(applicability_json)
                valid = (geometry.canonical_bytes.decode() == geometry_json
                         and geometry.address == geometry_address
                         and applicability.canonical_bytes.decode() == applicability_json
                         and applicability.address == applicability_address)
            except Exception:
                valid = False
            if not valid:
                raise CopyRefusal("chart annotation is not canonical closed presentation JSON")
    schedule_columns = {
        "positions": (("paper_entry_charge_schedule_id",
                       "paper_entry_charge_schedule_address"),),
        "trades": (
            ("paper_entry_charge_schedule_id", "paper_entry_charge_schedule_address"),
            ("paper_exit_charge_schedule_id", "paper_exit_charge_schedule_address"),
        ),
    }
    if set(schedule_columns) <= set(metadata.tables):
        reflected = inspect(connection)
        actual_tables = set(reflected.get_table_names())
        actual_columns = {
            table_name: {
                column["name"] for column in reflected.get_columns(table_name)
            }
            for table_name in schedule_columns
            if table_name in actual_tables
        }
        required_columns = {
            table_name: {
                name for pair in pairs for name in pair
            }
            for table_name, pairs in schedule_columns.items()
        }
        marker_heads = (
            list(connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalars()) if "alembic_version" in actual_tables else []
        )
        if (marker_heads != ["0044"]
                and "alembic_version" in actual_tables
                and all(required_columns[name] <= actual_columns.get(name, set())
                        for name in schedule_columns)):
            try:
                validate_paper_entry_lifecycle_manifest(connection)
            except RuntimeError as exc:
                if "trigger" in str(exc):
                    raise CopyRefusal(
                        "Paper entry intent immutability triggers are missing or invalid"
                    ) from exc
                raise CopyRefusal(
                    "Paper lifecycle schema manifest is invalid") from exc
        from app.engine.charges import ChargeScheduleRefusal, charge_schedule_address

        for table_name, pairs in schedule_columns.items():
            table = metadata.tables[table_name]
            selected = [table.c.id, table.c.mode]
            for schedule_id, schedule_address in pairs:
                selected.extend((table.c[schedule_id], table.c[schedule_address]))
            for row in connection.execute(sa.select(*selected)).mappings():
                for schedule_id, schedule_address in pairs:
                    identity = row[schedule_id]
                    address = row[schedule_address]
                    if (identity is None) != (address is None):
                        raise CopyRefusal(
                            f"{table_name} Paper charge schedule pair is incomplete")
                    if row["mode"] != "paper" and identity is not None:
                        raise CopyRefusal(
                            f"{table_name} live row carries Paper charge authority")
                    if identity is None:
                        continue
                    try:
                        expected = charge_schedule_address(identity)
                    except ChargeScheduleRefusal as exc:
                        raise CopyRefusal(
                            f"{table_name} Paper charge schedule is unknown") from exc
                    if address != expected:
                        raise CopyRefusal(
                            f"{table_name} Paper charge schedule address is invalid")
        _validate_paper_lifecycle_identity(connection, metadata)
    monitoring_tables = {
        "monitoring_assignments", "monitoring_state_snapshots",
        "monitoring_signal_events", "monitoring_signal_alerts",
        "monitoring_alert_delivery_attempts", "monitoring_alert_attention_events",
        "monitoring_latest_state", "monitoring_alert_attention_state",
        "monitoring_signal_reviews",
    }
    if monitoring_tables & set(metadata.tables):
        from app.monitoring.repository import (
            MonitoringPersistenceError, validate_persisted_monitoring,
        )
        try:
            validate_persisted_monitoring(connection)
        except MonitoringPersistenceError as exc:
            raise CopyRefusal("monitoring persistence identity or projection is invalid") from exc
    operations_tables = {name for name in metadata.tables if name.startswith("platform_")}
    if operations_tables:
        from app.platform_operations.repository import (
            OPERATIONS_TABLES, validate_persisted_operations,
        )
        from app.platform_operations.contracts import OperationsRefused
        if operations_tables != set(OPERATIONS_TABLES):
            raise CopyRefusal("platform operations table inventory is incomplete")
        try:
            validate_persisted_operations(connection)
        except OperationsRefused as exc:
            raise CopyRefusal("platform operations source or projection is invalid") from exc
    account_commerce_tables = {
        "account_profile_evidence", "account_trial_uses",
    }
    present_account_commerce = account_commerce_tables & set(
        sa.inspect(connection).get_table_names()
    )
    if present_account_commerce:
        from app.account_commerce.repository import (
            AccountCommerceRefused, validate_persisted_account_commerce,
        )
        if present_account_commerce != account_commerce_tables:
            raise CopyRefusal("account-commerce table inventory is incomplete")
        try:
            validate_persisted_account_commerce(connection)
        except AccountCommerceRefused as exc:
            raise CopyRefusal("account-commerce source or privacy facts are invalid") from exc
    if {"static_instrument_scopes", "static_instrument_scope_revisions"} & set(metadata.tables):
        from app.core.static_scopes import validate_persisted_scopes, ScopeInvalid, ScopeNotFound
        try:
            validate_persisted_scopes(connection)
        except (ScopeInvalid, ScopeNotFound) as exc:
            raise CopyRefusal("static scope identity or predecessor chain is invalid") from exc
    if "research_experiment_spec" in metadata.tables:
        import json as _json
        from research.orchestrator.run import spec_hash
        table = metadata.tables["research_experiment_spec"]
        for identifier, recipe in connection.execute(sa.select(table.c.id, table.c.recipe_json)):
            try:
                valid = spec_hash(_json.loads(recipe)) == identifier
            except Exception:
                valid = False
            if not valid:
                raise CopyRefusal("research experiment spec content address is invalid")
    if "backtest_computations" in metadata.tables:
        table = metadata.tables["backtest_computations"]
        for payload, digest in connection.execute(sa.select(table.c.payload_json, table.c.payload_digest)):
            if hashlib.sha256(payload.encode()).hexdigest() != digest:
                raise CopyRefusal("public computation payload digest is invalid")
    if "graph_versions" in metadata.tables:
        from app.ir.hashing import content_address
        import json as _json
        table = metadata.tables["graph_versions"]
        for artifact, address in connection.execute(sa.select(table.c.artifact_json, table.c.content_address)):
            try:
                valid = content_address(_json.loads(artifact)) == address
            except Exception:
                valid = False
            if not valid:
                raise CopyRefusal("graph version content address is invalid")
    if "project_review_snapshots" in metadata.tables:
        from app.core.review_snapshot import manifest_address_of_bytes
        table = metadata.tables["project_review_snapshots"]
        for manifest, address in connection.execute(sa.select(table.c.manifest_json, table.c.content_address)):
            if manifest_address_of_bytes(manifest) != address:
                raise CopyRefusal("review snapshot content address is invalid")


def _validate_paper_lifecycle_identity(connection, metadata: MetaData) -> None:
    """Require known Paper entry authority to resolve through one exact intent."""
    required = {"execution_intents", "positions", "trades"}
    if not required <= set(metadata.tables):
        return
    inspector = inspect(connection)
    if "alembic_version" in inspector.get_table_names():
        heads = list(connection.execute(text(
            "SELECT version_num FROM alembic_version"
        )).scalars())
        if heads == ["0044"]:
            # Closed monitoring compatibility permits an exact pre-Paper-charge
            # execution head. It cannot carry any 0045 schedule authority.
            for table_name in ("positions", "trades"):
                columns = {
                    column["name"] for column in inspector.get_columns(table_name)
                }
                if "paper_entry_charge_schedule_id" not in columns:
                    continue
                table = metadata.tables[table_name]
                if connection.scalar(sa.select(sa.func.count()).select_from(table).where(
                        table.c.paper_entry_charge_schedule_id.is_not(None))):
                    raise CopyRefusal(
                        "0044 cannot carry Paper entry charge authority")
            return
    required_triggers = {
        "positions_refuse_entry_intent_id_rebind",
        "trades_refuse_entry_intent_id_rebind",
    }
    if connection.dialect.name == "sqlite":
        actual_triggers = set(connection.execute(text(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )).scalars())
    elif connection.dialect.name == "postgresql":
        actual_triggers = set(connection.execute(text(
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
        )).scalars())
    else:
        raise CopyRefusal("Paper lifecycle identity requires SQLite or PostgreSQL")
    if required_triggers - actual_triggers:
        raise CopyRefusal("Paper entry intent immutability triggers are missing")
    intent_table = metadata.tables["execution_intents"]
    intents = {
        row["client_intent_id"]: row
        for row in connection.execute(sa.select(intent_table)).mappings()
    }
    groups: dict[str, list[dict[str, object]]] = {}
    fields = (
        "entry_intent_id", "owner_id", "broker_account_id", "deployment_id",
        "instrument_key", "tradingsymbol", "exchange", "segment", "direction",
        "entry_premium", "entry_time", "strategy_key", "strategy_version",
        "admission_address", "graph_address", "attribution_state", "qty",
    )
    for table_name in ("positions", "trades"):
        table = metadata.tables[table_name]
        statement = sa.select(*(table.c[name] for name in fields)).where(
            table.c.mode == "paper",
            table.c.paper_entry_charge_schedule_id.is_not(None),
        )
        for row in connection.execute(statement).mappings():
            intent_id = row["entry_intent_id"]
            if intent_id is None or intent_id not in intents:
                raise CopyRefusal(
                    f"{table_name} known Paper entry schedule lacks an intent")
            groups.setdefault(str(intent_id), []).append(dict(row))
    for intent_id, rows in groups.items():
        intent = intents[intent_id]
        anchor = rows[0]
        segment = anchor["segment"] or "options"
        side = "BUY" if segment == "options" else (
            "BUY" if anchor["direction"] == "LONG" else "SELL")
        product = "MIS" if segment == "equity_intraday" else (
            "NRML" if segment == "index_futures" else None)
        expected = {
            "owner_id": anchor["owner_id"],
            "broker_account_id": anchor["broker_account_id"],
            "deployment_id": anchor["deployment_id"],
            "intent": "ENTRY",
            "instrument_key": anchor["instrument_key"],
            "tradingsymbol": anchor["tradingsymbol"],
            "exchange": anchor["exchange"],
            "side": side,
            "product": product,
            "order_type": "MARKET",
            "limit_price": None,
            "decision_price": anchor["entry_premium"],
            "signal_at": anchor["entry_time"],
            "strategy_key": anchor["strategy_key"],
            "strategy_version": anchor["strategy_version"],
            "admission_address": anchor["admission_address"],
            "graph_address": anchor["graph_address"],
            "attribution_state": anchor["attribution_state"],
        }
        if any(intent[key] != value for key, value in expected.items()):
            raise CopyRefusal("Paper entry intent content or scope is inconsistent")
        sibling_fields = fields[1:-1]
        if any((row["segment"] or "options") != segment
               or any(row[field] != anchor[field] for field in sibling_fields)
               for row in rows):
            raise CopyRefusal("Paper entry intent joins inconsistent lifecycle rows")
        if sum(int(row["qty"]) for row in rows) != int(intent["requested_qty"]):
            raise CopyRefusal("Paper entry intent lifecycle quantity is inconsistent")


def _copy_one(plane: CopyPlane, *, batch_size: int,
              expected_source_snapshot: dict[str, object] | None = None) -> dict[str, object]:
    path = Path(plane.source_path)
    if not path.is_file():
        raise CopyRefusal(f"missing SQLite source for {plane.name}")
    if make_url(plane.destination_url).get_backend_name() != "postgresql":
        raise CopyRefusal(f"{plane.name} destination must be an explicit PostgreSQL URL")
    if (expected_source_snapshot is not None
            and _source_snapshot(path) != expected_source_snapshot):
        raise CopyRefusal(f"{plane.name} SQLite source changed since all-plane preflight")
    initial_db_stat = _file_snapshot(path).get("db")
    source = _source_engine(path)
    destination = sa.create_engine(plane.destination_url, future=True, pool_pre_ping=True)
    try:
        if inspect(destination).get_table_names():
            raise CopyRefusal(f"{plane.name} PostgreSQL destination is nonempty")
        source_head = _validate_source_schema(plane, source)
        source_stat = _file_snapshot(path)
        source_hash = _hash_source_files(path)
        if source_stat.get("db") != initial_db_stat:
            raise CopyRefusal(f"{plane.name} SQLite source changed during preflight")
        plane.initialize_destination(destination)
        plane.validate_destination(destination)
        if plane.name == "execution" and (plane.destination_head or plane.source_head) in {
                "0045", "0046", "0047", "0048"}:
            with destination.connect() as destination_connection:
                try:
                    validate_paper_entry_lifecycle_manifest(
                        destination_connection,
                        compatible_heads=frozenset({plane.destination_head or plane.source_head}),
                    )
                except RuntimeError as exc:
                    raise CopyRefusal(
                        "execution PostgreSQL Paper lifecycle manifest is invalid") from exc
        for table in plane.metadata.sorted_tables:
            with destination.connect() as connection:
                if connection.execute(sa.select(sa.func.count()).select_from(table)).scalar_one():
                    raise CopyRefusal(f"{plane.name} initialized destination contains payload")
        with source.connect() as source_connection:
            source_connection.exec_driver_sql("BEGIN")
            start_version = source_connection.exec_driver_sql("PRAGMA data_version").scalar_one()
            with destination.begin() as destination_connection:
                source_summary = {}
                for table in plane.metadata.sorted_tables:
                    source_summary[table.name] = _stream_summary(
                        source_connection, table, batch_size=batch_size,
                        destination=destination_connection,
                    )
                _validate_semantic_ownership(destination_connection, plane.metadata)
                _validate_credentials(destination_connection, plane.metadata)
                _validate_content_addresses(destination_connection, plane.metadata)
                _validate_postgresql_constraints(destination_connection)
                sequences = _repair_sequences(destination_connection, plane.metadata)
                destination_summary = {
                    table.name: _stream_summary(
                        destination_connection, table, batch_size=batch_size)
                    for table in plane.metadata.sorted_tables
                }
                if source_summary != destination_summary:
                    raise CopyRefusal(f"{plane.name} destination digest mismatch")
                end_version = source_connection.exec_driver_sql("PRAGMA data_version").scalar_one()
                if (start_version != end_version or source_stat != _file_snapshot(path)
                        or source_hash != _hash_source_files(path)):
                    raise CopyRefusal(f"{plane.name} SQLite source changed during copy")
            source_connection.rollback()
        plane.validate_destination(destination)
        return {
            "plane": plane.name, "source": _redacted_source(path),
            "destination": _redacted_destination(plane.destination_url),
            "source_head": source_head,
            "destination_head": plane.destination_head or plane.source_head,
            "source_file": {"sha256": source_hash, "stat": source_stat},
            "tables": source_summary, "sequences": sequences,
            "validation": {"schema": True, "foreign_keys": True,
                           "ownership": True, "digests": True, "credential_key": True},
        }
    finally:
        source.dispose()
        destination.dispose()


def _hash_source_files(path: Path) -> str:
    digest = hashlib.sha256()
    for suffix in ("", "-wal"):
        candidate = Path(f"{path}{suffix}")
        if not candidate.exists():
            continue
        digest.update((suffix or "db").encode() + b"\0")
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _source_snapshot(path: Path) -> dict[str, object]:
    return {"stat": _file_snapshot(path), "sha256": _hash_source_files(path)}


def copy_planes(planes: Iterable[CopyPlane], *, batch_size: int = 500) -> dict[str, object]:
    planes = list(planes)
    if not planes:
        raise CopyRefusal("at least one plane is required")
    if batch_size < 1:
        raise CopyRefusal("batch size must be positive")
    source_paths = [Path(plane.source_path) for plane in planes]
    if any(not path.is_absolute() for path in source_paths):
        raise CopyRefusal("SQLite source paths must be absolute")
    resolved_sources = [path.resolve() for path in source_paths]
    if len(set(resolved_sources)) != len(resolved_sources):
        raise CopyRefusal("SQLite source paths must be pairwise distinct")
    try:
        from research.guards import assert_pairwise_database_authorities
        if len(planes) == 3:
            assert_pairwise_database_authorities(*(plane.destination_url for plane in planes))
        elif len({str(make_url(plane.destination_url)) for plane in planes}) != len(planes):
            raise CopyRefusal("PostgreSQL destinations must be pairwise distinct")
    except CopyRefusal:
        raise
    except Exception as exc:
        raise CopyRefusal("PostgreSQL destinations must be pairwise distinct") from exc
    # Preflight every source before any destination authority is contacted.
    for plane in planes:
        if not Path(plane.source_path).is_file():
            raise CopyRefusal(f"missing SQLite source for {plane.name}")
    # Validate every source and every empty target before the first target schema is
    # created. This prevents a later-plane preflight failure from mutating an earlier
    # destination.
    for plane in planes:
        if make_url(plane.destination_url).get_backend_name() != "postgresql":
            raise CopyRefusal(f"{plane.name} destination must be an explicit PostgreSQL URL")
        source = _source_engine(Path(plane.source_path))
        destination = sa.create_engine(plane.destination_url, future=True, pool_pre_ping=True)
        try:
            _validate_source_schema(plane, source)
            if inspect(destination).get_table_names():
                raise CopyRefusal(f"{plane.name} PostgreSQL destination is nonempty")
        finally:
            source.dispose()
            destination.dispose()
    # Capture the cross-plane freeze boundary only after every source/target has
    # passed preflight. Each plane must still match this exact evidence immediately
    # before its destination schema is initialized.
    preflight_snapshots = [
        _source_snapshot(Path(plane.source_path)) for plane in planes
    ]
    started = dt.datetime.now(dt.timezone.utc)
    results = [_copy_one(
        plane, batch_size=batch_size,
        expected_source_snapshot=source_snapshot,
    ) for plane, source_snapshot in zip(planes, preflight_snapshots, strict=True)]
    _validate_cross_plane_semantics(planes)
    for plane, expected in zip(planes, preflight_snapshots, strict=True):
        if _source_snapshot(Path(plane.source_path)) != expected:
            raise CopyRefusal(
                f"{plane.name} SQLite source changed after sequential copy; "
                "all committed destinations from this run are quarantined"
            )
    report: dict[str, object] = {
        "tool": "sqlite-to-postgresql-copy", "tool_version": TOOL_VERSION,
        "build": _build_version(),
        "started_at": started.isoformat(),
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "batch_size": batch_size, "workload_rows": sum(
            table["rows"] for result in results for table in result["tables"].values()),
        "planes": results, "cutover_ready": True,
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    report["content_address"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return report


def _build_version() -> str:
    try:
        from app.core.version import get_build_sha
        return get_build_sha()
    except Exception:
        return "unknown"


def canonical_report(report: dict[str, object]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def _validate_sequences(connection, metadata: MetaData) -> list[dict[str, object]]:
    results = []
    for table in metadata.sorted_tables:
        for column in table.primary_key.columns:
            if not isinstance(column.type, sa.Integer) or len(table.primary_key.columns) != 1:
                continue
            sequence = connection.execute(text(
                "SELECT pg_get_serial_sequence(:table, :column)"
            ), {"table": table.name, "column": column.name}).scalar_one_or_none()
            if not sequence:
                continue
            maximum = connection.execute(sa.select(sa.func.max(column))).scalar_one()
            preparer = connection.dialect.identifier_preparer
            qualified = ".".join(preparer.quote(part) for part in sequence.split("."))
            state = connection.execute(text(
                f"SELECT last_value, is_called FROM {qualified}"
            )).one()
            next_value = int(state[0]) + (1 if state[1] else 0)
            if maximum is not None and next_value <= int(maximum):
                raise CopyRefusal(f"{table.name}.{column.name} sequence can collide")
            results.append({"table": table.name, "column": column.name,
                            "copied_max": maximum, "next_at_least": next_value})
    return results


# Stable, read-only integrity primitives shared with the PostgreSQL restore
# contract.  The copy workflow above remains SQLite-to-PostgreSQL; exporting
# these bounded primitives does not turn it into a backup verifier.
def stream_table_summary(connection, table: Table, *, batch_size: int = 500) -> dict[str, object]:
    return _stream_summary(connection, table, batch_size=batch_size)


def validate_semantic_ownership(connection, metadata: MetaData) -> None:
    _validate_semantic_ownership(connection, metadata)


def validate_content_addresses(connection, metadata: MetaData) -> None:
    _validate_content_addresses(connection, metadata)


def validate_postgresql_constraints(connection) -> None:
    _validate_postgresql_constraints(connection)


def validate_sequence_safety(connection, metadata: MetaData) -> list[dict[str, object]]:
    return _validate_sequences(connection, metadata)


def streamed_identity_set(connection, table: Table, columns: tuple[str, ...],
                          *, batch_size: int = 500) -> set[bytes]:
    return _streamed_identity_set(connection, table, columns, batch_size=batch_size)


def verify_planes(planes: Iterable[CopyPlane], report: dict[str, object]) -> None:
    """Recompute the report's load-bearing evidence without changing either side."""
    planes = list(planes)
    expected_planes = {item["plane"]: item for item in report.get("planes", [])}
    for plane in planes:
        expected = expected_planes.get(plane.name)
        if expected is None:
            raise CopyRefusal(f"report omits {plane.name} plane")
        source = _source_engine(Path(plane.source_path))
        destination = sa.create_engine(plane.destination_url, future=True, pool_pre_ping=True)
        try:
            _validate_source_schema(plane, source)
            plane.validate_destination(destination)
            with source.connect() as source_connection, destination.connect() as destination_connection:
                if plane.name == "execution" and (
                        plane.destination_head or plane.source_head) in {"0045", "0046", "0047", "0048"}:
                    try:
                        validate_paper_entry_lifecycle_manifest(
                            destination_connection,
                            compatible_heads=frozenset({
                                plane.destination_head or plane.source_head}),
                        )
                    except RuntimeError as exc:
                        raise CopyRefusal(
                            "execution PostgreSQL Paper lifecycle manifest is invalid") from exc
                _validate_semantic_ownership(destination_connection, plane.metadata)
                _validate_credentials(destination_connection, plane.metadata)
                _validate_content_addresses(destination_connection, plane.metadata)
                _validate_postgresql_constraints(destination_connection)
                source_summary = {table.name: _stream_summary(
                    source_connection, table, batch_size=500)
                    for table in plane.metadata.sorted_tables}
                destination_summary = {table.name: _stream_summary(
                    destination_connection, table, batch_size=500)
                    for table in plane.metadata.sorted_tables}
                if source_summary != destination_summary or source_summary != expected.get("tables"):
                    raise CopyRefusal(f"{plane.name} digest verification failed")
                actual_sequences = _validate_sequences(destination_connection, plane.metadata)
                if actual_sequences != expected.get("sequences"):
                    raise CopyRefusal(f"{plane.name} sequence inventory verification failed")
        finally:
            source.dispose()
            destination.dispose()
    _validate_cross_plane_semantics(planes)


def verify_report_content_address(report: dict[str, object]) -> None:
    unsigned = dict(report)
    supplied = unsigned.pop("content_address", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode()
    expected = "sha256:" + hashlib.sha256(canonical).hexdigest()
    if supplied != expected or report.get("cutover_ready") is not True:
        raise CopyRefusal("report content address or cutover status is invalid")


def configured_planes(*, execution_source: Path, execution_destination: str,
                      research_source: Path, research_destination: str,
                      ledger_source: Path, ledger_destination: str) -> list[CopyPlane]:
    """Bind the generic contract to the current, separate plane authorities."""
    from app.db.models import Base
    from app.db import migrate
    from app.ledger import models as _ledger_models  # noqa: F401
    from app.ledger.db import (HEAD_VERSION as LEDGER_HEAD, LedgerBase,
                              init_ledger_db)
    from research.domain import models as _research_models  # noqa: F401
    from research.domain.base import ResearchBase, init_research_db
    from research.domain.migrate import (HEAD_VERSION as RESEARCH_HEAD,
                                         _validate_postgresql as validate_research)
    from app.db.plane_schema import validate_postgresql_plane

    def init_execution(engine: Engine) -> None:
        migrate.init_schema(
            engine, create_all=lambda: Base.metadata.create_all(engine),
            legacy_migrate=lambda: (_ for _ in ()).throw(
                CopyRefusal("historical migration attempted on PostgreSQL destination")),
            expected_tables=Base.metadata.tables,
        )

    def validate_execution(engine: Engine) -> None:
        if migrate.schema_version(engine) != migrate.head_revision():
            raise CopyRefusal("execution PostgreSQL destination is not at head")
        migrate._validate_current_schema(engine, Base.metadata.tables)
        migrate._validate_postgresql_immutable_triggers(engine)

    def validate_research_engine(engine: Engine) -> None:
        with engine.connect() as connection:
            validate_research(connection)

    def validate_ledger_engine(engine: Engine) -> None:
        with engine.connect() as connection:
            validate_postgresql_plane(
                connection, LedgerBase.metadata,
                marker_table="ledger_schema_version", plane="ledger",
            )

    return [
        CopyPlane("execution", execution_source, execution_destination, Base.metadata,
                  "alembic_version", migrate.head_revision(), init_execution,
                  validate_execution, migrate.head_revision()),
        CopyPlane("research", research_source, research_destination, ResearchBase.metadata,
                  "research_schema_version", RESEARCH_HEAD, init_research_db,
                  validate_research_engine, RESEARCH_HEAD),
        CopyPlane("ledger", ledger_source, ledger_destination, LedgerBase.metadata,
                  None, "unversioned/current-model-validated", init_ledger_db,
                  validate_ledger_engine, LEDGER_HEAD),
    ]
