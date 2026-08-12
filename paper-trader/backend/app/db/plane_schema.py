"""Current-schema validation shared by the private PostgreSQL planes."""
from __future__ import annotations

import re

from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint, inspect


def _normalise_default(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"::(?:character varying|text|timestamp without time zone)$", "", str(value))
    return re.sub(r"\s+", "", text.strip().lower().strip("()"))


def _types_match(expected, actual) -> bool:
    if not expected._compare_type_affinity(actual):
        return False
    return all(
        getattr(expected, attr, None) is None
        or getattr(expected, attr, None) == getattr(actual, attr, None)
        for attr in ("length", "precision", "scale")
    )


def _canonical_check(expression: str) -> tuple | str:
    """Canonicalize the bounded CHECK grammar used by research and ledger.

    PostgreSQL deparses ``IN`` as ``= ANY (ARRAY[...])`` and adds text casts.
    Those are the only semantic aliases in the five private-plane checks. After
    rewriting them, exact token equality retains Boolean structure and rejects
    pass-through CASE/OR clauses rather than comparing a lossy bag of anchors.
    """
    value = expression.lower().replace('"', "")
    value = re.sub(
        r"::\s*(?:character varying|text)(?:\[\])?",
        "",
        value,
    )
    value = re.sub(
        r"\b([a-z_][a-z0-9_]*)\s*=\s*any\s*\(\s*array\[(.*?)\]\s*\)",
        lambda match: f"{match.group(1)} in ({match.group(2)})",
        value,
        flags=re.DOTALL,
    )
    value = re.sub(
        r"\bin\s*\(([^()]*)\)",
        lambda match: f"in[{match.group(1)}]",
        value,
        flags=re.DOTALL,
    ).rstrip(";")

    tokens = [
        token.strip() for token in re.split(r"(\band\b|\bor\b|\(|\))", value)
        if token.strip()
    ]
    position = 0

    def factor():
        nonlocal position
        if position < len(tokens) and tokens[position] == "(":
            position += 1
            node = disjunction()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("unbalanced CHECK expression")
            position += 1
            return node
        if position >= len(tokens) or tokens[position] in {"and", "or", ")"}:
            raise ValueError("invalid CHECK expression")
        atom = re.sub(r"\s+", "", tokens[position])
        position += 1
        return ("atom", atom)

    def conjunction():
        nonlocal position
        nodes = [factor()]
        while position < len(tokens) and tokens[position] == "and":
            position += 1
            child = factor()
            nodes.extend(child[1:] if child[0] == "and" else (child,))
        return nodes[0] if len(nodes) == 1 else ("and", *nodes)

    def disjunction():
        nonlocal position
        nodes = [conjunction()]
        while position < len(tokens) and tokens[position] == "or":
            position += 1
            child = conjunction()
            nodes.extend(child[1:] if child[0] == "or" else (child,))
        return nodes[0] if len(nodes) == 1 else ("or", *nodes)

    try:
        result = disjunction()
        if position != len(tokens):
            raise ValueError("trailing CHECK expression tokens")
        return result
    except ValueError:
        # An unsupported construct is not normalized into a known model CHECK;
        # exact compact text still makes a tampered CASE/function-like form fail.
        return re.sub(r"\s+", "", value)


def validate_postgresql_plane(connection, metadata, *, marker_table: str, plane: str) -> None:
    """Validate the exact tables and load-bearing reflected relational contract."""
    inspector = inspect(connection)
    expected_names = set(metadata.tables) | {marker_table}
    actual_names = set(inspector.get_table_names())
    if actual_names != expected_names:
        raise RuntimeError(
            f"{plane} PostgreSQL table-set drift: "
            f"{sorted(actual_names)} != {sorted(expected_names)}"
        )

    marker_columns = inspector.get_columns(marker_table)
    marker_pk = inspector.get_pk_constraint(marker_table).get("constrained_columns") or []
    if (len(marker_columns) != 1
            or marker_columns[0]["name"] != "version"
            or not _types_match(String(16), marker_columns[0]["type"])
            or marker_columns[0]["nullable"]
            or marker_pk != ["version"]):
        raise RuntimeError(f"{plane} PostgreSQL schema marker contract drift")

    defects = {}
    for name, table in metadata.tables.items():
        reflected = {column["name"]: column for column in inspector.get_columns(name)}
        table_defects = {}
        expected_column_names = {column.name for column in table.columns}
        if set(reflected) != expected_column_names:
            table_defects["columns"] = (sorted(expected_column_names), sorted(reflected))
        column_defects = {}
        for column in table.columns:
            actual = reflected.get(column.name)
            if actual is None:
                continue
            expected_default = _normalise_default(
                column.server_default.arg.compile(dialect=connection.dialect)
                if column.server_default is not None else None
            )
            actual_default = _normalise_default(actual.get("default"))
            serial_default = (
                column.primary_key and isinstance(column.type, Integer)
                and expected_default is None
                and actual_default is not None and actual_default.startswith("nextval(")
            )
            if (not _types_match(column.type, actual["type"])
                    or bool(column.nullable) != bool(actual["nullable"])
                    or (expected_default != actual_default and not serial_default)):
                column_defects[column.name] = {
                    "expected": (str(column.type), column.nullable, expected_default),
                    "actual": (str(actual["type"]), actual["nullable"], actual_default),
                }
        if column_defects:
            table_defects["column_contracts"] = column_defects

        expected_pk = tuple(column.name for column in table.primary_key.columns)
        actual_pk = tuple(inspector.get_pk_constraint(name).get("constrained_columns") or ())
        if actual_pk != expected_pk:
            table_defects["primary_key"] = (expected_pk, actual_pk)

        expected_fks = {
            (tuple(element.parent.name for element in constraint.elements),
             constraint.elements[0].column.table.name,
             tuple(element.column.name for element in constraint.elements),
             constraint.ondelete, constraint.onupdate)
            for constraint in table.foreign_key_constraints
        }
        actual_fks = {
            (tuple(fk["constrained_columns"]), fk["referred_table"],
             tuple(fk["referred_columns"]), (fk.get("options") or {}).get("ondelete"),
             (fk.get("options") or {}).get("onupdate"))
            for fk in inspector.get_foreign_keys(name)
        }
        if actual_fks != expected_fks:
            table_defects["foreign_keys"] = (expected_fks, actual_fks)

        expected_unique = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints if isinstance(constraint, UniqueConstraint)
        }
        reflected_uniques = inspector.get_unique_constraints(name)
        actual_unique = {
            tuple(constraint["column_names"])
            for constraint in reflected_uniques
        }
        if actual_unique != expected_unique:
            table_defects["unique_constraints"] = (expected_unique, actual_unique)

        expected_check_constraints = {
            constraint.name: constraint for constraint in table.constraints
            if isinstance(constraint, CheckConstraint) and constraint.name
        }
        actual_check_constraints = {
            constraint["name"]: constraint.get("sqltext") or ""
            for constraint in inspector.get_check_constraints(name)
            if constraint.get("name")
        }
        check_defects = {}
        if set(actual_check_constraints) != set(expected_check_constraints):
            check_defects["names"] = (
                set(expected_check_constraints), set(actual_check_constraints),
            )
        for constraint_name, constraint in expected_check_constraints.items():
            actual_expression = actual_check_constraints.get(constraint_name)
            if actual_expression is None:
                continue
            expected_expression = str(constraint.sqltext.compile(dialect=connection.dialect))
            if _canonical_check(expected_expression) != _canonical_check(actual_expression):
                check_defects[constraint_name] = {
                    "expected": expected_expression,
                    "actual": actual_expression,
                }
        if check_defects:
            table_defects["check_constraints"] = check_defects

        expected_indexes = {
            index.name: (tuple(column.name for column in index.columns), bool(index.unique))
            for index in table.indexes
        }
        unique_index_names = {
            constraint.get("name") for constraint in reflected_uniques
            if constraint.get("name")
        }
        actual_indexes = {
            index["name"]: (tuple(index["column_names"]), bool(index.get("unique")))
            for index in inspector.get_indexes(name)
            if index["name"] not in unique_index_names
        }
        if actual_indexes != expected_indexes:
            table_defects["indexes"] = (expected_indexes, actual_indexes)
        if table_defects:
            defects[name] = table_defects
    if defects:
        raise RuntimeError(f"{plane} PostgreSQL current-schema drift: {defects}")
