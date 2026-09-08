"""Data-parametric PostgreSQL 0010 witness builder.

The catalog comes solely from ``postgresql_0010_contract``.  Callers provide
their own rows and sequence state; neither is historical authority.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from research.domain.migrations import postgresql_0010_contract as contract


def _kind(statement: str) -> tuple[str, ...]:
    return tuple(statement.split(maxsplit=2)[:2])


def construct(connection: Any, *, marker: str = contract.CURRENT_MARKER) -> None:
    """Execute the frozen PostgreSQL DDL and stamp the requested supported marker."""
    connection.exec_driver_sql(contract.marker_ddl())
    statements = contract.durable_ddl()
    for statement in statements:
        if _kind(statement) == ("CREATE", "OR"):
            connection.exec_driver_sql(statement)
    tables = [statement for statement in statements if _kind(statement) == ("CREATE", "TABLE")]
    available = {"research_schema_version"}
    # The accepted inventory is lexical. Order table declarations solely from
    # their frozen foreign-key references before emitting the same bytes.
    while tables:
        ready = []
        for statement in tables:
            table = re.match(r"CREATE \w+ (\w+)", statement).group(1)
            references = set(re.findall(r"REFERENCES (\w+)", statement)) - {table}
            if references <= available:
                ready.append((table, statement))
        if not ready:
            raise ValueError("cyclic or missing frozen PostgreSQL table dependency")
        for table, statement in ready:
            connection.exec_driver_sql(statement)
            available.add(table)
            tables.remove(statement)
    for prefix in (("CREATE", "TRIGGER"), ("CREATE", "INDEX")):
        for statement in statements:
            if _kind(statement) == prefix:
                connection.exec_driver_sql(statement)
    for statement in statements:
        if _kind(statement) not in {("CREATE", "TABLE"), ("CREATE", "OR"), ("CREATE", "TRIGGER"), ("CREATE", "INDEX")}:
            raise ValueError(f"unclassified frozen PostgreSQL declaration: {statement[:48]!r}")
    connection.exec_driver_sql("DELETE FROM research_schema_version")
    connection.exec_driver_sql("INSERT INTO research_schema_version(version) VALUES (%s)", (marker,))


def seed(connection: Any, rows: Mapping[str, Sequence[Sequence[Any]]]) -> None:
    """Insert explicit witness values only; no defaults or sequence-advancing calls."""
    declarations = {item["name"]: item["columns"] for item in contract.CATALOG_0010["tables"]}
    for table, values in rows.items():
        if table == "research_schema_version":
            raise ValueError("witnesses cannot define marker authority")
        columns = declarations.get(table)
        if columns is None:
            raise ValueError(f"unknown witness table: {table}")
        for row in values:
            if len(row) != len(columns):
                raise ValueError(f"row width mismatch for {table}")
            placeholders = ",".join("%s" for _ in row)
            connection.exec_driver_sql(
                f'INSERT INTO "{table}" VALUES ({placeholders})',
                tuple(row),
            )


def set_sequence_state(connection: Any, name: str, last_value: int, called: bool) -> None:
    """Explicit test setup only; validation must inspect without ``nextval``."""
    connection.exec_driver_sql("SELECT setval(%s, %s, %s)", (name, last_value, called))


def _normal_type(value: str) -> str:
    return " ".join(value.lower().replace("character varying", "varchar").replace("float", "double precision").split())


def _normal_sql(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.replace("\n", " ").split()).lower()


def _normal_default(value: str | None) -> str | None:
    """Ignore PostgreSQL's implementation default for literal SERIAL only."""
    if value is None or value.startswith("nextval("):
        return None
    return re.sub(r"::[a-z_ ]+(?:\(\d+\))?", "", _normal_sql(value) or "")


def _stable_sorted(values: Sequence[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """Sort immutable tuples even where a frozen optional fact is ``None``."""
    return sorted(values, key=repr)


def _normal_check(value: str | None) -> str | None:
    if value is None:
        return None
    result = _normal_sql(value) or ""
    if result.startswith("check "):
        result = result[6:]
    while result.startswith("(") and result.endswith(")"):
        result = result[1:-1]
    return result.replace("::character varying", "")


def _semantic_signature(value: str | None) -> tuple[str, ...] | None:
    """Dialect-normalize stored definitions while retaining every SQL token."""
    if value is None:
        return None
    normalized = re.sub(r"::[a-z_ ]+(?:\[\])?(?:\(\d+\))?", "", value.lower())
    normalized = re.sub(r"=\s*any\s*\(\s*array\s*\[", " in (", normalized)
    tokens = re.findall(r"'[^']*'|[a-z_][a-z_0-9]*|\d+|>=|<=|<>|!=|~|=|>|<", normalized)
    # PostgreSQL may persist IN as ``= ANY (ARRAY[...])``.  Normalize the
    # complete operator triple while retaining every operand token.
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


def _function_definition_signature(value: str) -> tuple[Any, ...]:
    """Compare the stored function identity, language, arguments, and body.

    PostgreSQL's deparser may add ``public.`` and change the position of the
    LANGUAGE clause or dollar-quote tag.  Those are presentation details; the
    full executable body and all declared function facts remain comparable.
    """
    normalized = value.replace("%%", "%")
    identity = re.search(r"function\s+(?:public\.)?(\w+)\s*\(([^)]*)\)\s+returns\s+(\w+)", normalized, re.IGNORECASE)
    language = re.search(r"\blanguage\s+(\w+)", normalized, re.IGNORECASE)
    body = re.search(r"\bas\s+\$[^$]*\$(.*)\$[^$]*\$", normalized, re.IGNORECASE | re.DOTALL)
    if identity is None or language is None or body is None:
        raise AssertionError("PostgreSQL function definition was not readable")
    return (
        identity.group(1).lower(),
        _semantic_signature(identity.group(2)) or (),
        identity.group(3).lower(),
        language.group(1).lower(),
        _semantic_signature(body.group(1)) or (),
    )


def _trigger_definition_signature(value: str) -> tuple[Any, ...]:
    """Compare every trigger binding fact independent of deparser event order."""
    match = re.search(
        r"create\s+trigger\s+(\w+)\s+(before|after)\s+(.+?)\s+on\s+(?:public\.)?(\w+)\s+for\s+each\s+row\s+execute\s+function\s+(?:public\.)?(\w+)\s*\(([^)]*)\)",
        value,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise AssertionError("PostgreSQL trigger definition was not readable")
    events = tuple(sorted(event.lower() for event in re.findall(r"insert|update|delete|truncate", match.group(3), re.IGNORECASE)))
    return (match.group(1).lower(), match.group(2).lower(), events, match.group(4).lower(), match.group(5).lower(), _semantic_signature(match.group(6)) or ())


def _expected_sequence_names() -> list[str]:
    names: list[str] = []
    for statement in contract.durable_ddl():
        match = re.match(r"CREATE" + r" TABLE (\w+) \((.*)\)$", statement)
        if not match:
            continue
        table, declaration = match.groups()
        for column in re.findall(r"(?:^|,)\s*([a-z_]+) SERIAL(?: |,|$)", declaration):
            names.append(f"{table}_{column}_seq")
    return sorted(names)


def _expected_serial_bindings() -> list[tuple[str, str, str]]:
    bindings: list[tuple[str, str, str]] = []
    for statement in contract.durable_ddl():
        match = re.match(r"CREATE" + r" TABLE (\w+) \((.*)\)$", statement)
        if not match:
            continue
        table, declaration = match.groups()
        for column in re.findall(r"(?:^|,)\s*([a-z_]+) SERIAL(?: |,|$)", declaration):
            bindings.append((table, column, f"{table}_{column}_seq"))
    return sorted(bindings)


def _expected_catalog() -> dict[str, Any]:
    tables = contract.CATALOG_0010["tables"]
    columns = sorted(
        (table["name"], column["name"], _normal_type(column["type"]), not column["nullable"], _normal_default(column["server_default"]))
        for table in tables for column in table["columns"]
    )
    constraints = _stable_sorted(
        (table["name"], item["kind"], item["name"], tuple(item["columns"]),
         tuple(item.get("referred_columns", ())), _semantic_signature(_normal_check(item.get("expression"))))
        for table in tables for item in table["constraints"]
    )
    indexes = sorted(
        (table["name"], item["name"], tuple(item["columns"]), item["unique"], item["postgresql_where"])
        for table in tables for item in table["indexes"]
    )
    ddl = contract.durable_ddl()
    functions = _stable_sorted([
        (name, _normal_sql(statement))
        for statement in ddl if statement.startswith("CREATE OR REPLACE FUNCTION")
        for name in re.findall(r"CREATE OR REPLACE FUNCTION (\w+)", statement)
    ])
    triggers = _stable_sorted([
        (name, _normal_sql(statement))
        for statement in ddl if statement.startswith("CREATE TRIGGER")
        for name in re.findall(r"CREATE TRIGGER (\w+)", statement)
    ])
    return {"columns": columns, "constraints": constraints, "indexes": indexes,
            "sequences": _expected_sequence_names(), "serial_bindings": _expected_serial_bindings(), "functions": functions, "triggers": triggers,
            "declarations": len(ddl)}


def inventory(connection: Any) -> dict[str, Any]:
    """Read exact PostgreSQL durable state without calling nextval or mutating it."""
    tables = connection.exec_driver_sql(
        "SELECT tablename FROM pg_tables WHERE schemaname = %s AND tablename LIKE %s AND tablename <> %s ORDER BY tablename",
        (connection.exec_driver_sql("SELECT current_schema()").scalar_one(), "research_%", "research_schema_version"),
    ).scalars().all()
    result: dict[str, Any] = {
        "tables": tables,
        "columns": connection.exec_driver_sql(
            "SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,pg_get_expr(ad.adbin,ad.adrelid) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid LEFT JOIN pg_attrdef ad ON ad.adrelid=a.attrelid AND ad.adnum=a.attnum WHERE c.relnamespace=current_schema()::regnamespace AND c.relkind='r' AND c.relname LIKE %s AND c.relname <> %s AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum",
            ("research_%", "research_schema_version"),
        ).all(),
        "constraints": connection.exec_driver_sql(
            "SELECT c.relname,con.contype,CASE WHEN con.contype='p' THEN NULL ELSE con.conname END,COALESCE(array(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=k.attnum ORDER BY k.ord),array(SELECT a.attname FROM pg_depend d JOIN pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=d.refobjsubid WHERE d.classid='pg_constraint'::regclass AND d.objid=con.oid AND d.refobjid=con.conrelid AND d.refobjsubid>0 ORDER BY a.attnum),ARRAY[]::text[]),COALESCE(array(SELECT rc.relname||'.'||a.attname FROM unnest(con.confkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=con.confrelid AND a.attnum=k.attnum JOIN pg_class rc ON rc.oid=con.confrelid ORDER BY k.ord),ARRAY[]::text[]),pg_get_constraintdef(con.oid) FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid WHERE con.connamespace=current_schema()::regnamespace AND c.relname <> 'research_schema_version' ORDER BY 1,2,3"
        ).all(),
        "indexes": connection.exec_driver_sql(
            "SELECT c.relname,i.relname,ARRAY(SELECT a.attname FROM unnest(x.indkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum ORDER BY k.ord),x.indisunique,pg_get_expr(x.indpred,x.indrelid) FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid WHERE c.relnamespace=current_schema()::regnamespace AND i.relname LIKE 'ix_%%' ORDER BY 1,2"
        ).all(),
        "serial_bindings": connection.exec_driver_sql(
            "SELECT c.relname,a.attname,regexp_replace(pg_get_serial_sequence(c.oid::regclass::text,a.attname), '^.*\\.', '') FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid LEFT JOIN pg_attrdef ad ON ad.adrelid=a.attrelid AND ad.adnum=a.attnum WHERE c.relnamespace=current_schema()::regnamespace AND c.relkind='r' AND c.relname LIKE %s AND c.relname <> %s AND a.attnum>0 AND NOT a.attisdropped AND pg_get_expr(ad.adbin,ad.adrelid) LIKE 'nextval%%' ORDER BY 1,2",
            ("research_%", "research_schema_version"),
        ).all(),
    }
    sequences = connection.exec_driver_sql(
        "SELECT relname FROM pg_class WHERE relnamespace = current_schema()::regnamespace AND relkind = 'S' ORDER BY relname"
    ).scalars().all()
    result["sequences"] = [
        (name, *connection.exec_driver_sql(f'SELECT last_value,is_called FROM "{name}"').one())
        for name in sequences
    ]
    result["functions"] = connection.exec_driver_sql(
        "SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p WHERE p.pronamespace=current_schema()::regnamespace ORDER BY p.proname"
    ).all()
    result["triggers"] = connection.exec_driver_sql(
        "SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE t.tgrelid::regclass::text LIKE 'research_%%' AND NOT t.tgisinternal ORDER BY 1,2"
    ).all()
    result["declarations"] = len(tables) + len(result["indexes"]) + len(result["functions"]) + len(result["triggers"])
    for table in tables:
        result[table] = connection.exec_driver_sql(f'SELECT * FROM "{table}" ORDER BY 1').all()
    return result


def assert_complete_inventory(state: Mapping[str, Any], *, sequence_states: Mapping[str, tuple[int, bool]] | None = None) -> None:
    """Reject absent PostgreSQL durable tables or sequence state."""
    expected = sorted(table["name"] for table in contract.CATALOG_0010["tables"])
    if state["tables"] != expected or len(expected) != 24:
        raise AssertionError("PostgreSQL immutable table inventory differs")
    expected_catalog = _expected_catalog()
    observed_columns = sorted((table, column, _normal_type(kind), bool(required), _normal_default(default)) for table, column, kind, required, default in state["columns"])
    if observed_columns != expected_catalog["columns"]:
        raise AssertionError(f"PostgreSQL immutable column inventory differs: expected-only={sorted(set(expected_catalog['columns']) - set(observed_columns), key=repr)!r}; observed-only={sorted(set(observed_columns) - set(expected_catalog['columns']), key=repr)!r}")
    expected_names = {item[2] for item in expected_catalog["constraints"] if item[2] is not None}
    kinds = {"p": "PrimaryKeyConstraint", "f": "ForeignKeyConstraint", "u": "UniqueConstraint", "c": "CheckConstraint"}
    observed_constraints = _stable_sorted(
        # The frozen contract has no check-column declaration.  PostgreSQL's
        # dependency reader still observes it above, while the complete check
        # definition is the immutable comparable fact here.
        (table, kinds[kind], name if name in expected_names else None, () if kind == "c" else tuple(columns),
         tuple(referred),
         _semantic_signature(_normal_check(definition)) if kind == "c" else None)
        for table, kind, name, columns, referred, definition in state["constraints"]
    )
    if observed_constraints != expected_catalog["constraints"]:
        raise AssertionError(f"PostgreSQL immutable key/FK/check inventory differs: expected-only={_stable_sorted(tuple(set(expected_catalog['constraints']) - set(observed_constraints)))!r}; observed-only={_stable_sorted(tuple(set(observed_constraints) - set(expected_catalog['constraints'])))!r}")
    if sorted((table, name, tuple(columns), unique, where) for table, name, columns, unique, where in state["indexes"]) != expected_catalog["indexes"]:
        raise AssertionError("PostgreSQL immutable index inventory differs")
    # Keep the complete native tuples in the comparison path: callers may
    # assert explicit witness sequence states without consuming nextval.
    if state["sequences"] == []:
        raise AssertionError("PostgreSQL native sequence state is missing")
    if sorted(name for name, *_ in state["sequences"]) != expected_catalog["sequences"]:
        raise AssertionError("PostgreSQL exact native sequence inventory differs")
    if sorted(state["serial_bindings"]) != expected_catalog["serial_bindings"]:
        raise AssertionError("PostgreSQL immutable serial default binding differs")
    expected_functions = _stable_sorted((name, _function_definition_signature(definition)) for name, definition in expected_catalog["functions"])
    observed_functions = _stable_sorted((name, _function_definition_signature(definition)) for name, definition in state["functions"])
    if observed_functions != expected_functions:
        raise AssertionError("PostgreSQL immutable function definition inventory differs")
    expected_triggers = _stable_sorted((name, _trigger_definition_signature(definition)) for name, definition in expected_catalog["triggers"])
    observed_triggers = _stable_sorted((name, _trigger_definition_signature(definition)) for _, name, definition in state["triggers"])
    if observed_triggers != expected_triggers:
        raise AssertionError("PostgreSQL immutable trigger binding/definition inventory differs")
    if state["declarations"] != expected_catalog["declarations"] or state["declarations"] != 67:
        raise AssertionError("PostgreSQL immutable declaration inventory differs")
    if sequence_states is not None and sorted(state["sequences"]) != sorted((name, *value) for name, value in sequence_states.items()):
        raise AssertionError("PostgreSQL caller-declared native sequence state differs")
