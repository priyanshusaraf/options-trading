"""Conservative, dialect-aware schema semantic comparison.

This module is the single authority for comparing reflected CHECK expressions
and complete trigger/function definitions.  It recognises only the closed
SQLite/PostgreSQL spellings emitted by the accepted migrations; it never parses,
evaluates, reorders, associates, or otherwise simplifies SQL.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

import sqlalchemy as sa


def normalise_schema_sql(value: Any) -> str | None:
    """Preserved non-CHECK schema spelling normalisation."""
    if value is None:
        return None
    result = "".join(str(value).lower().replace('"', "").split())
    result = result.replace("timestampwithouttimezone", "timestamp")
    result = result.replace("::text", "")
    result = re.sub(r"cast\(([a-z_][a-z0-9_]*)asjsonb\)", r"\1::jsonb", result)
    result = re.sub(r"\(([a-z_][a-z0-9_]*::jsonb->'[^']+')\)", r"\1", result)
    return strip_whole_check_wrappers(result)


def compact_sql(value: Any, *, identifiers: frozenset[str], comments: bool = False) -> str:
    """Fold whitespace/case outside literals and exact known identifier quotes."""
    source = str(value)
    result: list[str] = []
    index = 0
    while index < len(source):
        character = source[index]
        if comments and source.startswith("--", index):
            newline = source.find("\n", index + 2)
            index = len(source) if newline < 0 else newline + 1
            continue
        if comments and source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise ValueError("unterminated SQL comment")
            index = end + 2
            continue
        if character == "'":
            start = index
            index += 1
            while index < len(source):
                if source[index] == "'":
                    index += 1
                    if index < len(source) and source[index] == "'":
                        index += 1
                        continue
                    break
                index += 1
            if source[index - 1:index] != "'":
                raise ValueError("unterminated SQL literal")
            result.append(source[start:index])
            continue
        if character == '"':
            index += 1
            quoted: list[str] = []
            terminated = False
            while index < len(source):
                if source[index] == '"':
                    index += 1
                    if index < len(source) and source[index] == '"':
                        quoted.append('"')
                        index += 1
                        continue
                    terminated = True
                    break
                quoted.append(source[index])
                index += 1
            name = "".join(quoted)
            if not terminated or name not in identifiers:
                # Preserve the accepted monitoring comparator's observable
                # refusal text while the implementation now serves both users.
                raise ValueError(f"quoted identifier outside monitoring metadata: {name!r}")
            result.append(name)
            continue
        if character.isspace():
            index += 1
            continue
        result.append(character.lower())
        index += 1
    return "".join(result)


def strip_whole_check_wrappers(value: str) -> str:
    """Remove only balanced parentheses enclosing the complete expression."""
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        encloses_all = True
        in_literal = False
        index = 0
        while index < len(value):
            character = value[index]
            if character == "'":
                if in_literal and index + 1 < len(value) and value[index + 1] == "'":
                    index += 2
                    continue
                in_literal = not in_literal
            elif not in_literal:
                depth += (character == "(") - (character == ")")
                if depth < 0:
                    return value
                if depth == 0 and index != len(value) - 1:
                    encloses_all = False
                    break
            index += 1
        if in_literal or depth != 0 or not encloses_all:
            break
        value = value[1:-1]
    return value


def _shield_literals(value: str) -> tuple[str, tuple[str, ...]]:
    parts: list[str] = []
    literals: list[str] = []
    index = 0
    start = 0
    while index < len(value):
        if value[index] != "'":
            index += 1
            continue
        parts.append(value[start:index])
        literal_start = index
        index += 1
        while index < len(value):
            if value[index] != "'":
                index += 1
                continue
            index += 1
            if index < len(value) and value[index] == "'":
                index += 1
                continue
            break
        if value[index - 1:index] != "'":
            raise ValueError("unterminated SQL literal")
        literals.append(value[literal_start:index])
        parts.append(f"\ue000{len(literals) - 1}\ue001")
        start = index
    parts.append(value[start:])
    return "".join(parts), tuple(literals)


def _restore_literals(value: str, literals: tuple[str, ...]) -> str:
    def restore(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if index >= len(literals):
            raise ValueError("unknown SQL literal shield token")
        return literals[index]
    return re.sub(r"\ue000([0-9]+)\ue001", restore, value)


def conservative_check_sql(
    value: Any,
    *,
    identifiers: frozenset[str],
    string_identifiers: frozenset[str],
    postgresql: bool = True,
    allow_branch_wrapper: bool = False,
    allow_nullable_regex_wrapper: bool = False,
    allow_numeric_peer_coercion: bool = False,
    allow_and_arm_wrapper: bool = False,
    allow_not_equal_synonym: bool = False,
) -> str:
    result = strip_whole_check_wrappers(
        compact_sql(value, identifiers=identifiers, comments=True))
    if not postgresql:
        return result
    result, literals = _shield_literals(result)
    literal_token = r"\ue000[0-9]+\ue001"
    result = re.sub(
        r"cast\(([a-z_][a-z0-9_]*)asjsonb\)",
        lambda match: f"{match.group(1)}::jsonb"
        if match.group(1) in identifiers else match.group(0), result)
    restore_literal = rf"{literal_token}::charactervarying::text"
    for identifier in sorted(string_identifiers, key=len, reverse=True):
        result = re.sub(
            rf"\b{re.escape(identifier)}::text=any\(array\["
            rf"({restore_literal}(?:,{restore_literal})*)\]\)",
            lambda match, name=identifier: (
                f"{name}in(" + match.group(1).replace("::charactervarying::text", "") + ")"),
            result)
    for identifier in sorted(string_identifiers, key=len, reverse=True):
        result = result.replace(f"{identifier}::text", identifier)
    result = re.sub(rf"({literal_token})::charactervarying", r"\1", result)
    result = re.sub(rf"({literal_token})::text(?!\[)", r"\1", result)
    for identifier in sorted(string_identifiers, key=len, reverse=True):
        result = re.sub(
            rf"\b{re.escape(identifier)}=any\(array\["
            rf"({literal_token}(?:,{literal_token})*)\]::text\[\]\)",
            rf"{identifier}in(\1)", result)
    for index, literal in enumerate(literals):
        if literal == "'{}'":
            result = result.replace(f"\ue000{index}\ue001::text[]", f"\ue000{index}\ue001")
    result = re.sub(rf"\(([a-z_][a-z0-9_]*::jsonb->{literal_token})\)", r"\1", result)
    result = re.sub(rf"\(([a-z_][a-z0-9_]*::jsonb->>{literal_token})\)", r"\1", result)
    if allow_branch_wrapper:
        match = re.fullmatch(r"\(([^()]*)\)or\(([^()]*)\)", result)
        if match and all("and" in branch for branch in match.groups()):
            result = f"{match.group(1)}or{match.group(2)}"
    if allow_nullable_regex_wrapper:
        result = re.sub(
            rf"\b([a-z_][a-z0-9_]*)isnullor\(\1~({literal_token})\)",
            r"\1isnullor\1~\2", result)
    if allow_numeric_peer_coercion:
        result = re.sub(
            rf"\(\(([^()]+#>>{literal_token})\)::numeric\)="
            r"([a-z_][a-z0-9_]*)::numeric", r"(\1)::numeric=\2", result)
    if allow_and_arm_wrapper:
        # PostgreSQL removes only the redundant wrapper around the right-hand
        # AND operand of OR.  No other parentheses are removed.
        result = re.sub(r"^([^()]+or)\(([^()]*and[^()]*)\)$", r"\1\2", result)
    if allow_not_equal_synonym:
        result = result.replace("!=", "<>")
    return _restore_literals(result, literals)


def check_sql_matches(
    table: sa.Table, constraint_name: str | None, dialect_name: str,
    expected: Any, actual: Any, *, context: str = "monitoring",
) -> bool:
    identifiers = frozenset(column.name for column in table.columns)
    string_identifiers = frozenset(
        column.name for column in table.columns if isinstance(column.type, sa.String))
    options = {
        "identifiers": identifiers,
        "string_identifiers": string_identifiers,
        "postgresql": dialect_name == "postgresql",
        "allow_branch_wrapper": context == "monitoring" and constraint_name in {
            "ck_monitoring_assignments_withdrawal", "ck_monitoring_delivery_failure",
            "ck_monitoring_snapshots_predecessor"},
        "allow_nullable_regex_wrapper": context == "monitoring" and constraint_name in {
            "ck_monitoring_assignments_current_snapshot", "ck_monitoring_latest_event",
            "ck_monitoring_snapshots_predecessor_address"},
        "allow_numeric_peer_coercion": (
            context == "monitoring" and constraint_name == "ck_monitoring_snapshots_json_sequence"),
        "allow_and_arm_wrapper": context == "paper" and constraint_name in {
            "ck_positions_paper_charge_mode", "ck_trades_paper_charge_mode"},
        "allow_not_equal_synonym": context == "paper" and constraint_name in {
            "ck_positions_paper_entry_intent_required",
            "ck_trades_paper_entry_intent_required"},
    }
    try:
        expected_compact = strip_whole_check_wrappers(
            compact_sql(expected, identifiers=identifiers, comments=True))
        actual_compact = strip_whole_check_wrappers(
            compact_sql(actual, identifiers=identifiers, comments=True))
        if _shield_literals(expected_compact)[1] != _shield_literals(actual_compact)[1]:
            return False
        return conservative_check_sql(expected, **options) == conservative_check_sql(actual, **options)
    except ValueError:
        return False


def full_sql_matches(expected: Any, actual: Any, *, identifiers: frozenset[str]) -> bool:
    """Compare a complete trigger/function body with comment-only no-ops."""
    try:
        return compact_sql(expected, identifiers=identifiers, comments=True) == compact_sql(
            actual, identifiers=identifiers, comments=True)
    except ValueError:
        return False


def _paper_address_check(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return f"{column} is null or {column} ~ '^sha256:[0-9a-f]{{64}}$'"
    return (
        f"{column} is null or (length({column}) = 71 and substr({column}, 1, 7) = "
        f"'sha256:' and substr({column}, 8) = lower(substr({column}, 8)) and "
        f"substr({column}, 8) not glob '*[^0-9a-f]*')")


def expected_paper_checks(dialect: str) -> dict[str, dict[str, str]]:
    return {
        "positions": {
            "ck_positions_paper_entry_charge_pair":
                "(paper_entry_charge_schedule_id is null) = "
                "(paper_entry_charge_schedule_address is null)",
            "ck_positions_paper_entry_charge_address":
                _paper_address_check("paper_entry_charge_schedule_address", dialect),
            "ck_positions_paper_charge_mode":
                "mode = 'paper' or (paper_entry_charge_schedule_id is null and "
                "paper_entry_charge_schedule_address is null)",
            "ck_positions_paper_entry_intent_required":
                "mode != 'paper' or paper_entry_charge_schedule_id is null or "
                "entry_intent_id is not null",
        },
        "trades": {
            "ck_trades_paper_entry_charge_pair":
                "(paper_entry_charge_schedule_id is null) = "
                "(paper_entry_charge_schedule_address is null)",
            "ck_trades_paper_exit_charge_pair":
                "(paper_exit_charge_schedule_id is null) = "
                "(paper_exit_charge_schedule_address is null)",
            "ck_trades_paper_entry_charge_address":
                _paper_address_check("paper_entry_charge_schedule_address", dialect),
            "ck_trades_paper_exit_charge_address":
                _paper_address_check("paper_exit_charge_schedule_address", dialect),
            "ck_trades_paper_charge_mode":
                "mode = 'paper' or (paper_entry_charge_schedule_id is null and "
                "paper_entry_charge_schedule_address is null and "
                "paper_exit_charge_schedule_id is null and "
                "paper_exit_charge_schedule_address is null)",
            "ck_trades_paper_entry_intent_required":
                "mode != 'paper' or paper_entry_charge_schedule_id is null or "
                "entry_intent_id is not null",
        },
    }


def validate_paper_entry_lifecycle_manifest(
    connection, *, compatible_heads: frozenset[str] = frozenset({"0045", "0046", "0047", "0048"}),
) -> None:
    """Validate accepted Paper semantics at every compatible additive head."""
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Paper lifecycle guard requires SQLite or PostgreSQL")
    heads = list(connection.execute(sa.text(
        "SELECT version_num FROM alembic_version")).scalars())
    if len(heads) != 1 or heads[0] not in compatible_heads:
        raise RuntimeError("Paper lifecycle migration marker is not compatible")
    inspector = sa.inspect(connection)
    expected_checks = expected_paper_checks(dialect)
    for table_name, expected in expected_checks.items():
        table = sa.Table(table_name, sa.MetaData(), autoload_with=connection)
        actual = {
            item.get("name"): item.get("sqltext")
            for item in inspector.get_check_constraints(table_name)
            if item.get("name") in expected
        }
        if set(actual) != set(expected) or any(
            not check_sql_matches(
                table, name, dialect, expected_sql, actual[name], context="paper")
            for name, expected_sql in expected.items()
        ):
            raise RuntimeError(f"Paper lifecycle {table_name} CHECK manifest is not accepted")
    for table_name in ("positions", "trades"):
        _validate_paper_trigger(connection, table_name)


def _validate_paper_trigger(connection, table_name: str) -> None:
    trigger = f"{table_name}_refuse_entry_intent_id_rebind"
    function = f"{trigger}_fn"
    message = f"{table_name} entry_intent_id is immutable"
    identifiers = frozenset({
        table_name, trigger, function, "new", "old", "entry_intent_id"})
    if connection.dialect.name == "sqlite":
        rows = connection.execute(sa.text(
            "SELECT tbl_name,sql FROM sqlite_master WHERE type='trigger' AND name=:name"),
            {"name": trigger}).all()
        expected = (
            f"create trigger {trigger} before update on {table_name} "
            "when new.entry_intent_id is not old.entry_intent_id begin "
            f"select raise(abort, '{message}'); end")
        if (len(rows) != 1 or rows[0].tbl_name != table_name
                or not full_sql_matches(expected, rows[0].sql, identifiers=identifiers)):
            raise RuntimeError(f"Paper lifecycle {table_name} trigger is not accepted")
        return
    row = connection.execute(sa.text("""
        SELECT ns.nspname AS schema_name, rel.relname AS table_name,
               trg.tgname, trg.tgenabled, trg.tgtype, trg.tgisinternal,
               trg.tgdeferrable, trg.tginitdeferred, trg.tgnargs,
               encode(trg.tgargs, 'hex') AS trigger_arguments,
               trg.tgattr::text AS update_columns,
               pg_get_expr(trg.tgqual, trg.tgrelid) AS when_clause,
               trg.tgoldtable, trg.tgnewtable,
               pg_get_triggerdef(trg.oid, true) AS trigger_definition,
               pns.nspname AS function_schema, proc.proname AS function_name,
               proc.prokind, proc.pronargs, pg_get_function_arguments(proc.oid) AS arguments,
               pg_get_function_result(proc.oid) AS result, lang.lanname AS language,
               proc.provolatile, proc.proisstrict, proc.prosecdef, proc.proleakproof,
               proc.proparallel, proc.proconfig, proc.prosrc
        FROM pg_trigger trg
        JOIN pg_class rel ON rel.oid=trg.tgrelid
        JOIN pg_namespace ns ON ns.oid=rel.relnamespace
        JOIN pg_proc proc ON proc.oid=trg.tgfoid
        JOIN pg_namespace pns ON pns.oid=proc.pronamespace
        JOIN pg_language lang ON lang.oid=proc.prolang
        WHERE ns.nspname=current_schema() AND rel.relname=:table AND trg.tgname=:trigger
    """), {"table": table_name, "trigger": trigger}).mappings().all()
    expected_body = (
        "begin if new.entry_intent_id is distinct from old.entry_intent_id then "
        f"raise exception '{message}'; end if; return new; end;")
    if len(row) != 1:
        raise RuntimeError(f"Paper lifecycle {table_name} trigger is not accepted")
    actual = row[0]
    expected_metadata = {
        "schema_name": connection.dialect.default_schema_name,
        "table_name": table_name, "tgname": trigger, "tgenabled": "O", "tgtype": 19,
        "tgisinternal": False, "tgdeferrable": False, "tginitdeferred": False,
        "tgnargs": 0, "trigger_arguments": "", "update_columns": "", "when_clause": None,
        "tgoldtable": None, "tgnewtable": None,
        "function_schema": connection.dialect.default_schema_name,
        "function_name": function, "prokind": "f", "pronargs": 0,
        "arguments": "", "result": "trigger", "language": "plpgsql",
        "provolatile": "v", "proisstrict": False, "prosecdef": False,
        "proleakproof": False, "proparallel": "u", "proconfig": None,
    }
    expected_trigger = (
        f"create trigger {trigger} before update on {table_name} for each row "
        f"execute function {function}()")
    if not _postgresql_trigger_function_matches(
            actual, expected_metadata=expected_metadata,
            expected_trigger=expected_trigger, expected_body=expected_body,
            identifiers=identifiers):
        raise RuntimeError(f"Paper lifecycle {table_name} trigger is not accepted")


def _postgresql_trigger_function_matches(
    actual: Mapping[str, Any], *, expected_metadata: Mapping[str, Any],
    expected_trigger: str, expected_body: str, identifiers: frozenset[str],
) -> bool:
    """Compare every declared trigger/function catalog field and complete SQL."""
    return (
        all(actual.get(key) == value for key, value in expected_metadata.items())
        and full_sql_matches(
            expected_trigger, actual.get("trigger_definition"), identifiers=identifiers)
        and full_sql_matches(expected_body, actual.get("prosrc"), identifiers=identifiers)
    )


__all__ = [
    "check_sql_matches", "compact_sql", "conservative_check_sql",
    "expected_paper_checks", "full_sql_matches", "normalise_schema_sql",
    "strip_whole_check_wrappers", "validate_paper_entry_lifecycle_manifest",
]
