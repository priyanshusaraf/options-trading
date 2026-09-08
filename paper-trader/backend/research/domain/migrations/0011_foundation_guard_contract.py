"""Finite direct migration from the frozen research 0010 catalogs to 0011.

Only three starts are supported: an empty schema, the exact frozen 0010
catalog, and the exact 0011 catalog.  Catalog authority comes from the frozen
dialect declarations beside this module, never from current ORM metadata.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from research.domain.migrations import postgresql_0010_contract as postgresql
from research.domain.migrations import sqlite_catalog_contract as sqlite


CURRENT_VERSION = "0010"
TARGET_VERSION = "0011"
VERSION_TABLE = "research_schema_version"
_SQLITE_ATTESTATION = "c47a7a626812574f4b87238cec9314168d40315da51ccc079561c6cc1f5c4b17"
_POSTGRESQL_ATTESTATION = "22b38890d481f1a75b8ba9424753f2ffe3b2c3cb912be3f015c3187a9e58d33a"
_REFUSAL = (
    "Back up the database, then use a read-only diagnostic/export against the "
    "recorded version or rebuild a clean research database. No marker rewrite, "
    "arbitrary repair, or downgrade is supported."
)


class FoundationMigrationError(RuntimeError):
    """The finite 0011 migration refused before changing durable state."""


# Tests replace this callable to simulate process interruption after all target
# guards exist but before marker advancement.  Both dialects invoke it inside
# the migration transaction.
_before_marker_advance: Callable[[Any], None] = lambda _connection: None


def _refuse(reason: str) -> None:
    raise FoundationMigrationError(f"Research migration refused: {reason}. {_REFUSAL}")


def _certify_frozen_authority() -> None:
    if sqlite.catalog_attestation() != _SQLITE_ATTESTATION:
        _refuse("the frozen SQLite catalog authority is corrupted")
    if postgresql.catalog_attestation() != _POSTGRESQL_ATTESTATION:
        _refuse("the frozen PostgreSQL catalog authority is corrupted")
    if (
        sqlite.CATALOG["marker_contract"]["current"] != CURRENT_VERSION
        or sqlite.CATALOG["marker_contract"]["target"] != TARGET_VERSION
        or postgresql.CURRENT_MARKER != CURRENT_VERSION
        or postgresql.TARGET_MARKER != TARGET_VERSION
    ):
        _refuse("the frozen marker authority is corrupted")


def _sqlite_schema(connection: Any) -> set[tuple[Any, ...]]:
    return set(connection.exec_driver_sql(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
    ).all())


def _sqlite_expected_schema() -> set[tuple[Any, ...]]:
    return {
        (item["type"], item["name"], item["table"], item["sql"])
        for item in sqlite.INVENTORY["sqlite_schema"]
    }


def _sqlite_marker(connection: Any) -> tuple[str, int]:
    columns = tuple(connection.exec_driver_sql(
        f'PRAGMA table_info("{VERSION_TABLE}")'
    ).all())
    expected = (
        (0, "version", "VARCHAR(16)", 1, None, 1),
        (1, "schema_cookie", "INTEGER", 1, None, 0),
    )
    if columns != expected:
        _refuse("the SQLite marker shape is corrupted or drifted")
    rows = connection.exec_driver_sql(
        f'SELECT version,schema_cookie FROM "{VERSION_TABLE}"'
    ).all()
    if len(rows) != 1:
        _refuse("the SQLite marker is missing, duplicated, or corrupted")
    return str(rows[0][0]), int(rows[0][1])


def _validate_sqlite_catalog(
    connection: Any, *, allow_missing_guards: bool,
) -> tuple[str, ...]:
    expected = _sqlite_expected_schema()
    actual = _sqlite_schema(connection)
    missing = expected - actual
    extra = actual - expected
    allowed = {
        item
        for item in expected
        if item[0] == "trigger" and item[1] in sqlite.REPAIRABLE_GUARDS
    }
    if extra or (missing - allowed if allow_missing_guards else missing):
        _refuse(
            "the SQLite catalog is drifted, corrupted, partial, or a hybrid "
            f"(missing={sorted((missing - allowed) if allow_missing_guards else missing, key=repr)!r}, "
            f"extra={sorted(extra, key=repr)!r})"
        )
    missing_names = tuple(sorted(item[1] for item in missing))
    if any(name not in sqlite.REPAIRABLE_GUARDS for name in missing_names):
        _refuse("the SQLite 0010 guard prefix is not an enumerated state")
    if int(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()) != 1:
        _refuse("SQLite foreign-key enforcement is disabled")
    return missing_names


def _sqlite_empty(connection: Any) -> bool:
    names = connection.exec_driver_sql(
        "SELECT name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'"
    ).scalars().all()
    return not names


def upgrade_sqlite(connection: Any) -> None:
    """Atomically install or certify 0011 on SQLite."""
    _certify_frozen_authority()
    # Connection-local enforcement is not durable database state.  Enable it
    # before the first possible DDL or DML statement, then certify it below.
    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    if _sqlite_empty(connection):
        # Python's sqlite3 legacy transaction mode does not begin a database
        # transaction for DDL.  Start one explicitly so trigger installation,
        # certification, and marker advancement are one atomic unit.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        for statement in sqlite.construct_sql():
            connection.exec_driver_sql(statement)
        _validate_sqlite_catalog(connection, allow_missing_guards=False)
        _before_marker_advance(connection)
        cookie = int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one())
        connection.exec_driver_sql(
            f'INSERT INTO "{VERSION_TABLE}"(version,schema_cookie) VALUES (?,?)',
            (TARGET_VERSION, cookie),
        )
        return

    actual_names = set(connection.exec_driver_sql(
        "SELECT name FROM sqlite_schema WHERE type='table'"
    ).scalars())
    if VERSION_TABLE not in actual_names:
        _refuse("the populated SQLite database is unversioned")
    version, marker_cookie = _sqlite_marker(connection)
    actual_cookie = int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one())
    if marker_cookie != actual_cookie:
        _refuse(
            "the SQLite (version, schema_cookie) marker is stale, downgraded, "
            "or inconsistent with the catalog"
        )
    if version == TARGET_VERSION:
        _validate_sqlite_catalog(connection, allow_missing_guards=False)
        return
    if version != CURRENT_VERSION:
        _refuse(f"unsupported SQLite research version {version!r}")

    missing_guards = _validate_sqlite_catalog(connection, allow_missing_guards=True)
    connection.exec_driver_sql("BEGIN IMMEDIATE")
    # Recheck under the write lock before making the first durable change.
    if _sqlite_marker(connection) != (CURRENT_VERSION, marker_cookie):
        _refuse("the SQLite marker changed during migration preflight")
    if int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one()) != marker_cookie:
        _refuse("the SQLite catalog changed during migration preflight")
    missing_guards = _validate_sqlite_catalog(connection, allow_missing_guards=True)
    for name in missing_guards:
        connection.exec_driver_sql(sqlite.GUARD_DDL[name])
    _validate_sqlite_catalog(connection, allow_missing_guards=False)
    _before_marker_advance(connection)
    cookie = int(connection.exec_driver_sql("PRAGMA schema_version").scalar_one())
    connection.exec_driver_sql(
        f'UPDATE "{VERSION_TABLE}" SET version=?,schema_cookie=?',
        (TARGET_VERSION, cookie),
    )


def _kind(statement: str) -> tuple[str, ...]:
    return tuple(statement.split(maxsplit=2)[:2])


def _construct_postgresql_0010(connection: Any) -> None:
    connection.exec_driver_sql(postgresql.marker_ddl())
    statements = postgresql.durable_ddl()
    for statement in statements:
        if _kind(statement) == ("CREATE", "OR"):
            connection.exec_driver_sql(statement)
    tables = [statement for statement in statements if _kind(statement) == ("CREATE", "TABLE")]
    available = {VERSION_TABLE}
    while tables:
        ready: list[tuple[str, str]] = []
        for statement in tables:
            match = re.match(r"CREATE \w+ (\w+)", statement)
            if match is None:
                _refuse("the frozen PostgreSQL table declaration is unreadable")
            table = match.group(1)
            references = set(re.findall(r"REFERENCES (\w+)", statement)) - {table}
            if references <= available:
                ready.append((table, statement))
        if not ready:
            _refuse("the frozen PostgreSQL table dependency order is invalid")
        for table, statement in ready:
            connection.exec_driver_sql(statement)
            available.add(table)
            tables.remove(statement)
    for prefix in (("CREATE", "TRIGGER"), ("CREATE", "INDEX")):
        for statement in statements:
            if _kind(statement) == prefix:
                connection.exec_driver_sql(statement)


def _normal_type(value: str) -> str:
    return " ".join(value.lower().replace("character varying", "varchar").replace("float", "double precision").split())


def _normal_sql(value: str | None) -> str | None:
    return None if value is None else " ".join(value.replace("\n", " ").split()).lower()


def _normal_default(value: str | None) -> str | None:
    if value is None or value.startswith("nextval("):
        return None
    return re.sub(r"::[a-z_ ]+(?:\(\d+\))?", "", _normal_sql(value) or "")


def _normal_check(value: str | None) -> str | None:
    result = _normal_sql(value)
    if result is None:
        return None
    if result.startswith("check "):
        result = result[6:]
    while result.startswith("(") and result.endswith(")"):
        result = result[1:-1]
    return result.replace("::character varying", "")


def _semantic_signature(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    normalized = re.sub(r"::[a-z_ ]+(?:\[\])?(?:\(\d+\))?", "", value.lower())
    tokens = re.findall(r"'[^']*'|[a-z_][a-z_0-9]*|\d+|>=|<=|<>|!=|~|=|>|<", normalized)
    result: list[str] = []
    position = 0
    while position < len(tokens):
        if tokens[position:position + 3] == ["=", "any", "array"]:
            result.append("in")
            position += 3
        else:
            result.append(tokens[position])
            position += 1
    return tuple(result)


def _function_signature(value: str) -> tuple[Any, ...]:
    normalized = value.replace("%%", "%")
    identity = re.search(r'function\s+(?:(?:"?\w+"?)\.)?(\w+)\s*\(([^)]*)\)\s+returns\s+(\w+)', normalized, re.I)
    language = re.search(r"\blanguage\s+(\w+)", normalized, re.I)
    body = re.search(r"\bas\s+\$[^$]*\$(.*)\$[^$]*\$", normalized, re.I | re.S)
    if identity is None or language is None or body is None:
        _refuse("a PostgreSQL function definition is unreadable")
    return (
        identity.group(1).lower(), _semantic_signature(identity.group(2)) or (),
        identity.group(3).lower(), language.group(1).lower(),
        _semantic_signature(body.group(1)) or (),
    )


def _trigger_signature(value: str) -> tuple[Any, ...]:
    match = re.search(
        r'create\s+trigger\s+(\w+)\s+(before|after)\s+(.+?)\s+on\s+(?:(?:"?\w+"?)\.)?(\w+)\s+for\s+each\s+row\s+execute\s+function\s+(?:(?:"?\w+"?)\.)?(\w+)\s*\(([^)]*)\)',
        value, re.I | re.S,
    )
    if match is None:
        _refuse("a PostgreSQL trigger definition is unreadable")
    events = tuple(sorted(event.lower() for event in re.findall(r"insert|update|delete|truncate", match.group(3), re.I)))
    return (match.group(1).lower(), match.group(2).lower(), events, match.group(4).lower(), match.group(5).lower(), _semantic_signature(match.group(6)) or ())


def _expected_postgresql_catalog() -> dict[str, Any]:
    tables = postgresql.CATALOG_0010["tables"]
    constraints = sorted((
        (
            table["name"], item["kind"], item["name"], tuple(item["columns"]),
            tuple(item.get("referred_columns", ())),
            _semantic_signature(_normal_check(item.get("expression"))),
        )
        for table in tables for item in table["constraints"]
    ), key=repr)
    ddl = postgresql.durable_ddl()
    functions = sorted((_function_signature(statement),) for statement in ddl if statement.startswith("CREATE OR REPLACE FUNCTION"))
    triggers = sorted((_trigger_signature(statement),) for statement in ddl if statement.startswith("CREATE TRIGGER"))
    sequences: list[str] = []
    bindings: list[tuple[str, str, str]] = []
    for statement in ddl:
        match = re.match(r"CREATE TABLE (\w+) \((.*)\)$", statement)
        if match:
            for column in re.findall(r"(?:^|,)\s*([a-z_]+) SERIAL(?: |,|$)", match.group(2)):
                name = f"{match.group(1)}_{column}_seq"
                sequences.append(name)
                bindings.append((match.group(1), column, name))
    return {
        "tables": sorted(table["name"] for table in tables),
        "views": [],
        "materialized_views": [],
        "columns": sorted((table["name"], column["name"], _normal_type(column["type"]), not column["nullable"], _normal_default(column["server_default"])) for table in tables for column in table["columns"]),
        "constraints": constraints,
        "indexes": sorted((table["name"], item["name"], tuple(item["columns"]), (), item["unique"], "btree", item["postgresql_where"]) for table in tables for item in table["indexes"]),
        "sequences": sorted(sequences), "bindings": sorted(bindings),
        "functions": functions, "triggers": triggers,
    }


def _observe_postgresql_catalog(connection: Any) -> dict[str, Any]:
    tables = connection.exec_driver_sql(
        "SELECT tablename FROM pg_tables WHERE schemaname=current_schema() AND tablename<>%s ORDER BY tablename",
        (VERSION_TABLE,),
    ).scalars().all()
    views = connection.exec_driver_sql(
        "SELECT viewname FROM pg_views WHERE schemaname=current_schema() ORDER BY viewname"
    ).scalars().all()
    materialized_views = connection.exec_driver_sql(
        "SELECT matviewname FROM pg_matviews WHERE schemaname=current_schema() ORDER BY matviewname"
    ).scalars().all()
    columns = connection.exec_driver_sql(
        "SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,pg_get_expr(ad.adbin,ad.adrelid) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid LEFT JOIN pg_attrdef ad ON ad.adrelid=a.attrelid AND ad.adnum=a.attnum WHERE c.relnamespace=current_schema()::regnamespace AND c.relkind='r' AND c.relname<>%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum",
        (VERSION_TABLE,),
    ).all()
    constraints = connection.exec_driver_sql(
        "SELECT c.relname,con.contype,CASE WHEN con.contype='p' THEN NULL ELSE con.conname END,COALESCE(array(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=k.attnum ORDER BY k.ord),array(SELECT a.attname FROM pg_depend d JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=d.refobjsubid WHERE d.classid='pg_constraint'::regclass AND d.objid=con.oid AND d.refobjid=con.conrelid AND d.refobjsubid>0 ORDER BY a.attnum),ARRAY[]::text[]),COALESCE(array(SELECT rc.relname||'.'||a.attname FROM unnest(con.confkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=con.confrelid AND a.attnum=k.attnum JOIN pg_class rc ON rc.oid=con.confrelid ORDER BY k.ord),ARRAY[]::text[]),pg_get_constraintdef(con.oid) FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid WHERE con.connamespace=current_schema()::regnamespace AND c.relname<>'research_schema_version' ORDER BY 1,2,3"
    ).all()
    indexes = connection.exec_driver_sql(
        "SELECT c.relname,i.relname,"
        "ARRAY(SELECT a.attname FROM unnest(x.indkey) WITH ORDINALITY k(attnum,ord) LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum WHERE k.ord<=x.indnkeyatts ORDER BY k.ord),"
        "ARRAY(SELECT a.attname FROM unnest(x.indkey) WITH ORDINALITY k(attnum,ord) LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum WHERE k.ord>x.indnkeyatts ORDER BY k.ord),"
        "x.indisunique,am.amname,pg_get_expr(x.indpred,x.indrelid) "
        "FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid "
        "JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_am am ON am.oid=i.relam "
        "LEFT JOIN pg_constraint owned ON owned.conindid=x.indexrelid "
        "AND owned.connamespace=current_schema()::regnamespace "
        "WHERE c.relnamespace=current_schema()::regnamespace AND owned.oid IS NULL ORDER BY 1,2"
    ).all()
    bindings = connection.exec_driver_sql(
        "SELECT c.relname,a.attname,regexp_replace(pg_get_serial_sequence(c.oid::regclass::text,a.attname), '^.*\\.', '') FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid LEFT JOIN pg_attrdef ad ON ad.adrelid=a.attrelid AND ad.adnum=a.attnum WHERE c.relnamespace=current_schema()::regnamespace AND c.relkind='r' AND c.relname<>%s AND a.attnum>0 AND NOT a.attisdropped AND pg_get_expr(ad.adbin,ad.adrelid) LIKE 'nextval%%' ORDER BY 1,2",
        (VERSION_TABLE,),
    ).all()
    sequence_names = connection.exec_driver_sql(
        "SELECT relname FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='S' ORDER BY relname"
    ).scalars().all()
    functions = connection.exec_driver_sql(
        "SELECT pg_get_functiondef(p.oid) FROM pg_proc p WHERE p.pronamespace=current_schema()::regnamespace ORDER BY p.proname"
    ).scalars().all()
    triggers = connection.exec_driver_sql(
        "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE c.relnamespace=current_schema()::regnamespace AND NOT t.tgisinternal ORDER BY c.relname,t.tgname"
    ).scalars().all()
    expected_names = {item[2] for item in _expected_postgresql_catalog()["constraints"] if item[2] is not None}
    kinds = {"p": "PrimaryKeyConstraint", "f": "ForeignKeyConstraint", "u": "UniqueConstraint", "c": "CheckConstraint"}
    return {
        "tables": list(tables),
        "views": list(views),
        "materialized_views": list(materialized_views),
        "columns": sorted((table, column, _normal_type(kind), bool(required), _normal_default(default)) for table, column, kind, required, default in columns),
        "constraints": sorted(((table, kinds[kind], name if name in expected_names else None, () if kind == "c" else tuple(columns_), tuple(referred), _semantic_signature(_normal_check(definition)) if kind == "c" else None) for table, kind, name, columns_, referred, definition in constraints), key=repr),
        "indexes": sorted((table, name, tuple(columns_), tuple(included), unique, method, where) for table, name, columns_, included, unique, method, where in indexes),
        "sequences": sorted(sequence_names), "bindings": sorted(tuple(row) for row in bindings),
        "functions": sorted((_function_signature(value),) for value in functions),
        "triggers": sorted((_trigger_signature(value),) for value in triggers),
    }


def _postgresql_marker(connection: Any) -> str:
    columns = connection.exec_driver_sql(
        "SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
        (VERSION_TABLE,),
    ).all()
    if columns != [("version", "character varying", "NO")]:
        _refuse("the PostgreSQL version-only marker shape is corrupted or drifted")
    rows = connection.exec_driver_sql(f'SELECT version FROM "{VERSION_TABLE}"').scalars().all()
    if len(rows) != 1:
        _refuse("the PostgreSQL marker is missing, duplicated, or corrupted")
    return str(rows[0])


def _validate_postgresql_catalog(connection: Any) -> None:
    if _observe_postgresql_catalog(connection) != _expected_postgresql_catalog():
        _refuse("the PostgreSQL catalog is drifted, corrupted, partial, or hybrid")


def upgrade_postgresql(connection: Any) -> None:
    """Atomically install or certify 0011 on PostgreSQL 16."""
    _certify_frozen_authority()
    major = int(connection.exec_driver_sql("SHOW server_version_num").scalar_one()) // 10000
    if major != 16:
        _refuse(f"PostgreSQL major {major} is unsupported; exact major 16 is required")
    objects = connection.exec_driver_sql(
        "SELECT relname FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind IN ('r','S','v','m') ORDER BY relname"
    ).scalars().all()
    functions = connection.exec_driver_sql(
        "SELECT proname FROM pg_proc WHERE pronamespace=current_schema()::regnamespace ORDER BY proname"
    ).scalars().all()
    if not objects and not functions:
        _construct_postgresql_0010(connection)
        _validate_postgresql_catalog(connection)
        _before_marker_advance(connection)
        connection.exec_driver_sql(
            f'INSERT INTO "{VERSION_TABLE}"(version) VALUES (%s)', (TARGET_VERSION,)
        )
        return
    if VERSION_TABLE not in objects:
        _refuse("the populated PostgreSQL database is unversioned")
    version = _postgresql_marker(connection)
    if version not in {CURRENT_VERSION, TARGET_VERSION}:
        _refuse(f"unsupported PostgreSQL research version {version!r}")
    _validate_postgresql_catalog(connection)
    if version == TARGET_VERSION:
        return
    _before_marker_advance(connection)
    connection.exec_driver_sql(
        f'UPDATE "{VERSION_TABLE}" SET version=%s', (TARGET_VERSION,)
    )


def downgrade(_connection: Any) -> None:
    _refuse("0011 downgrade is unsupported")
