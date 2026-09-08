"""Versioned schema migrations for the execution database.

This replaces the additive `ADD COLUMN` dict in `session.py` as the mechanism for
schema change. That dict still runs — it is the only thing that can carry a
database written before Alembic existed up to the baseline — but it is frozen
(see `tests/test_migrate_schema_frozen.py`). New columns, renames, type changes,
constraints and backfills are Alembic revisions from here on.

Three states a database can be in, and what happens to each
-----------------------------------------------------------
1. **Empty** (no tables) — a fresh dev/test database. `create_all()` builds the
   current model schema directly, then we STAMP head. No revision is executed,
   because the models already describe head. Fast, and it keeps the existing
   test-suite behaviour byte-for-byte.

2. **Populated, no `alembic_version`** — the owner's live `paper_trader.db`, and
   every database that existed before this commit. The frozen `_migrate_schema()`
   brings it to the baseline, we STAMP `0001`, then upgrade to head. Nothing is
   dropped and nothing is rebuilt: a pre-Alembic production ledger keeps every row.

3. **Populated, has `alembic_version`** — upgrade to head. The normal path forever
   after.

The invariant that makes (1) and (2) safe to coexist is that they must converge:
a database built by `create_all` and a database migrated up from the baseline must
have *identical* schemas. That is not assumed, it is asserted on every run of
`tests/test_schema_migrations.py`, which builds both and diffs them column by
column. If a future revision is written without the matching model change (or vice
versa), that test fails.
"""
from __future__ import annotations

import datetime as dt
import os
import re

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, Engine, Integer, UniqueConstraint, inspect
from sqlalchemy import text as _sa_text

from app.db.schema_semantics import (
    check_sql_matches,
    validate_paper_entry_lifecycle_manifest as _validate_paper_entry_lifecycle_manifest,
)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALEMBIC_INI = os.path.join(_BACKEND_DIR, "alembic.ini")
MIGRATIONS_DIR = os.path.join(_BACKEND_DIR, "migrations")
BASELINE_REVISION = "0001"
BASELINE_SCHEMA_SQL = os.path.join(MIGRATIONS_DIR, "baseline_schema.ddl")
POSTGRESQL_IMMUTABLE_TABLES = (
    "execution_order_events", "graph_versions", "project_review_snapshots", "strategy_admissions",
    "workspace_research_settings_revisions", "strategy_research_settings_revisions",
    "owner_provider_instrument_selections", "watchlist_monitoring_revisions",
)

# The tables that existed at revision 0001 — the documented inventory of the
# baseline. Adoption does not read this (it executes baseline_schema.ddl directly);
# it exists so the baseline's contents are reviewable in code, and
# `test_schema_migrations.py` asserts it still matches the DDL. A mismatch means
# the DDL was regenerated against newer models, which would silently move the
# floor every revision is measured from.
BASELINE_TABLES = frozenset({
    "backtest_results", "backtest_runs", "capital_state", "daily_account_snapshot",
    "earnings_events", "equity_snapshots", "generated_strategies", "instrument_state",
    "option_data", "order_journal", "positions", "runtime_config", "signal_events",
    "strategy_lifecycle", "trades", "universe_instruments", "watchlist_membership",
    "watchlists",
})


def validate_paper_entry_lifecycle_manifest(
    connection, *,
    compatible_heads: frozenset[str] = frozenset({
        "0045", "0046", "0047", "0048", "0049", "0050",
        "0051", "0052", "0053", "0054", "0055", "0056",
    }),
) -> None:
    """Bind the unchanged Paper manifest to every accepted additive head."""
    _validate_paper_entry_lifecycle_manifest(
        connection, compatible_heads=compatible_heads)


def alembic_config(connection=None) -> Config:
    """Alembic config bound to `connection` (never to a URL — see alembic.ini)."""
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("script_location", MIGRATIONS_DIR)
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def head_revision() -> str:
    """The newest revision on disk — what a fully-migrated database should report."""
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def schema_version(engine: Engine) -> str | None:
    """The revision this database is stamped at, or None if it is unmanaged.

    None is meaningful and is not an error: it means a pre-Alembic database that
    `init_schema` has not yet adopted.
    """
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def schema_state(engine: Engine) -> dict:
    """Schema version report for the health endpoint.

    `current` is what the database says; `head` is what this build expects. They
    differ exactly when a process is running against a database it has not
    migrated — which is a deploy-ordering fault worth seeing from outside.
    """
    current = schema_version(engine)
    head = head_revision()
    return {"current": current, "head": head, "up_to_date": current == head}


def _has_tables(engine: Engine) -> bool:
    names = set(inspect(engine).get_table_names())
    names.discard("alembic_version")
    return bool(names)


def _upgrade_research_settings(engine: Engine) -> str | None:
    return _upgrade_locked_addition(engine, "0052", "0051")


def _upgrade_locked_addition(engine, target, source):
    with engine.begin() as connection:
        if _is_postgresql(engine):
            connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
            connection.exec_driver_sql(f"SELECT pg_advisory_xact_lock({4200000 + int(target)})")
        else:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        heads = tuple(MigrationContext.configure(connection).get_current_heads())
        if heads == (target,):
            return target
        if heads != (source,):
            raise RuntimeError(f"{target} managed upgrade requires exact accepted {source} source")
        validate_paper_entry_lifecycle_manifest(connection, compatible_heads=frozenset({source}))
        command.upgrade(alembic_config(connection), target)
    return schema_version(engine)


def _upgrade_response_aliases(engine):
    if _is_postgresql(engine):
        return _upgrade_locked_addition(engine, "0055", "0054")
    with engine.connect() as connection:
        raw = connection.connection.driver_connection
        enabled = bool(raw.execute("PRAGMA foreign_keys").fetchone()[0])
        try:
            raw.execute("PRAGMA foreign_keys=OFF")
            with connection.begin():
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                heads = tuple(MigrationContext.configure(connection).get_current_heads())
                if heads == ("0055",):
                    return "0055"
                _require_managed_predecessor(heads, "0055", "0054")
                validate_paper_entry_lifecycle_manifest(connection, compatible_heads=frozenset({"0054"}))
                command.upgrade(alembic_config(connection), "0055")
        finally:
            connection.rollback()
            raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")
    return schema_version(engine)


def _upgrade_watchlist_monitoring(engine):
    # 0055 must retain its own SQLite FK suspension and commit boundary.
    if schema_version(engine) == "0054":
        _upgrade_response_aliases(engine)
    return _upgrade_locked_addition(engine, "0056", "0055")


_MANAGED_PREDECESSORS = {
    "0046": "0045", "0047": "0046", "0048": "0047",
    "0049": "0048", "0050": "0049", "0051": "0050",
}


def _require_managed_predecessor(heads, target, source):
    if heads != (source,):
        raise RuntimeError(
            f"{target} managed upgrade requires one exact accepted {source} source; "
            f"found heads={list(heads)}")


def _validate_paper_head(engine, head):
    with engine.connect() as connection:
        validate_paper_entry_lifecycle_manifest(connection, compatible_heads=frozenset({head}))


def _coupon_head_ready(engine, target):
    if target == "0049":
        _validate_coupon_dynamic_validity_readiness(engine, _current_model_tables())


def _managed_head_is_current(engine, target, source):
    with engine.connect() as connection:
        heads = tuple(MigrationContext.configure(connection).get_current_heads())
    if heads == (target,):
        if target == "0046":
            _validate_paper_head(engine, target)
        _coupon_head_ready(engine, target)
        return True
    _require_managed_predecessor(heads, target, source)
    _validate_paper_head(engine, source)
    return False


def _upgrade_postgresql_successor(engine, target, source):
    with engine.begin() as connection:
        connection.exec_driver_sql(f"SELECT pg_advisory_xact_lock({4200000 + int(target)})")
        heads = tuple(connection.execute(_sa_text(
            "SELECT version_num FROM alembic_version ORDER BY version_num"
        )).scalars())
        if heads == (target,):
            raise RuntimeError(
                f"{target} concurrent migration owner found head already advanced to {target}")
        _require_managed_predecessor(heads, target, source)
        validate_paper_entry_lifecycle_manifest(connection, compatible_heads=frozenset({source}))
        command.upgrade(alembic_config(connection), "head")
    _coupon_head_ready(engine, target)
    return schema_version(engine)


def upgrade_to_head(engine: Engine) -> str | None:
    """Dispatch the existing finite managed transitions through Alembic."""
    target = head_revision()
    managed = {"0052": _upgrade_research_settings, "0055": _upgrade_response_aliases,
               "0056": _upgrade_watchlist_monitoring}
    if target in managed:
        return managed[target](engine)
    additions = {"0053": "0052", "0054": "0053"}
    if target in additions:
        return _upgrade_locked_addition(engine, target, additions[target])
    source = _MANAGED_PREDECESSORS.get(target)
    if source is not None and _managed_head_is_current(engine, target, source):
        return target
    if target in {"0049", "0050", "0051"} and _is_postgresql(engine):
        return _upgrade_postgresql_successor(engine, target, source)
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "head")
    current = schema_version(engine)
    _coupon_head_ready(engine, target)
    return current


def stamp(engine: Engine, revision: str) -> None:
    """Record `revision` without executing it — for adopting an existing schema."""
    with engine.begin() as conn:
        command.stamp(alembic_config(conn), revision)


def _create_baseline_tables(engine: Engine) -> None:
    """Create any BASELINE table this database is missing — and nothing newer.

    Built from `baseline_schema.ddl`, NOT from the ORM models, and the distinction
    is the whole point. The models describe HEAD; a database being adopted is at the
    baseline and about to be walked forward by the revisions. Creating a "baseline"
    table from head-shaped models produces a table that already has every later
    revision's columns, and the revision that adds one then dies on `duplicate
    column name`. That is not theoretical — it is how revision 0002 failed the first
    time it met the adoption path.

    Why create anything at all: a database old enough to predate a table (one
    written before `watchlists` existed, say) never had it, and `_migrate_schema`
    only ever added COLUMNS. Before Alembic, `create_all` ran on every boot and
    quietly covered this; adoption happens once, so it has to be covered here.

    IF NOT EXISTS everywhere: for the normal case — a database that has all of them
    — this is a no-op.
    """
    with open(BASELINE_SCHEMA_SQL) as fh:
        ddl = "\n".join(line for line in fh.read().splitlines()
                        if not line.strip().startswith("--"))
    with engine.begin() as conn:
        for stmt in (s.strip() for s in ddl.split(";")):
            if not stmt:
                continue
            stmt = stmt.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1) \
                       .replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1) \
                       .replace("CREATE UNIQUE INDEX ",
                                "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
            conn.execute(_sa_text(stmt))


def _is_postgresql(engine: Engine) -> bool:
    return engine.dialect.name == "postgresql"


def _normalize_default(value) -> str | None:
    """Compare server-default literals across the PostgreSQL catalog deparser."""
    if value is None:
        return None
    value = "".join(str(value).split())
    # PostgreSQL records string literals with their inferred type, e.g.
    # ``'active'::character varying``. The literal is the contract here; the
    # catalog's implementation cast is not.
    value = re.sub(
        r"::(?:character(?:varying)?|varchar|text|boolean|integer|bigint|"
        r"doubleprecision|numeric|timestamp(?:withouttimezone)?)", "", value,
        flags=re.IGNORECASE,
    )
    while value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        value = value[1:-1]
    return value.lower()


def _compiled_sql(value, dialect) -> str | None:
    if value is None:
        return None
    return str(value.compile(dialect=dialect)) if hasattr(value, "compile") else str(value)


def _types_are_compatible(expected, actual) -> bool:
    """Use SQLAlchemy type affinity, retaining load-bearing declared limits."""
    if hasattr(expected, "_compare_type_affinity") and hasattr(actual, "_type_affinity"):
        if not expected._compare_type_affinity(actual):
            return False
        for attr in ("length", "precision", "scale"):
            expected_value = getattr(expected, attr, None)
            if expected_value is not None and expected_value != getattr(actual, attr, None):
                return False
        return True

    # Lightweight inspector fakes supply compiled strings. Keep their aliases
    # close to SQLAlchemy's PostgreSQL type affinity rather than comparing DDL.
    aliases = {
        "datetime": "timestamp",
        "timestampwithouttimezone": "timestamp",
        "float": "doubleprecision",
        # LargeBinary compiles to BLOB on SQLite and BYTEA on PostgreSQL; the
        # reflected-PG side reports the compiled string, so the affinity pair
        # is declared here rather than failing every binary column.
        "blob": "bytea",
    }
    expected_name = aliases.get("".join(str(expected).lower().split()),
                                "".join(str(expected).lower().split()))
    actual_name = aliases.get("".join(str(actual).lower().split()),
                              "".join(str(actual).lower().split()))
    return expected_name == actual_name


def _defaults_are_equivalent(column, expected, actual, dialect_name: str) -> bool:
    if expected == actual:
        return True
    # PostgreSQL implements an auto-increment integer primary key with a sequence
    # default even when the ORM has no explicit server default.
    return (
        dialect_name == "postgresql"
        and expected is None
        and bool(column.primary_key)
        and isinstance(column.type, Integer)
        and actual is not None
        and actual.startswith("nextval(")
    )


def _validate_strategy_admission_immutable_trigger(connection) -> None:
    """Reject a same-name trigger that no longer protects admission receipts."""
    row = connection.execute(_sa_text("""
        SELECT trigger.tgenabled, trigger.tgtype, trigger.tgqual IS NULL AS has_no_when,
               relation_namespace.nspname AS relation_schema,
               function_namespace.nspname AS function_schema,
               procedure.proname, procedure.prosrc, pg_get_triggerdef(trigger.oid) AS trigger_definition
        FROM pg_trigger AS trigger
        JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
        JOIN pg_namespace AS relation_namespace ON relation_namespace.oid = relation.relnamespace
        JOIN pg_proc AS procedure ON procedure.oid = trigger.tgfoid
        JOIN pg_namespace AS function_namespace ON function_namespace.oid = procedure.pronamespace
        WHERE NOT trigger.tgisinternal
          AND relation.relname = 'strategy_admissions'
          AND relation_namespace.nspname = current_schema()
          AND trigger.tgname = 'strategy_admissions_refuse_mutation'
    """)).mappings().one_or_none()
    expected_source = (
        "begin raise exception 'strategy admissions are immutable' "
        "using errcode = '55000'; end;"
    )
    # PostgreSQL: ROW (1) | BEFORE (2) | DELETE (8) | UPDATE (16).
    if (row is None or row["tgenabled"] != "O" or row["tgtype"] != 27
            or not row["has_no_when"]
            or row["relation_schema"] != row["function_schema"]
            or row["proname"] != "strategy_admissions_refuse_mutation"
            or " ".join(str(row["prosrc"]).lower().split()) != expected_source
            or "execute function strategy_admissions_refuse_mutation()" not in " ".join(
                str(row["trigger_definition"]).lower().split())):
        raise RuntimeError("strategy_admissions immutable-trigger contract is invalid")


def _validate_postgresql_immutable_triggers(engine: Engine) -> None:
    """Require append-only facts and the full receipt-trigger contract at startup."""
    expected = {f"{table}_refuse_mutation" for table in POSTGRESQL_IMMUTABLE_TABLES}
    with engine.connect() as connection:
        actual = set(connection.execute(_sa_text("""
            SELECT trigger.tgname
            FROM pg_trigger AS trigger
            JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
            WHERE NOT trigger.tgisinternal
              AND relation.relname = ANY(:tables)
        """), {"tables": list(POSTGRESQL_IMMUTABLE_TABLES)}).scalars())
    missing = expected - actual
    if missing:
        raise RuntimeError(
            "PostgreSQL immutable-fact triggers are missing: "
            f"{sorted(missing)}"
        )
    with engine.connect() as connection:
        _validate_strategy_admission_immutable_trigger(connection)


_COUPON_READINESS_TABLES = (
    "platform_coupon_definitions",
    "platform_coupon_redemptions",
    "platform_entitlement_events",
)
_COUPON_SQLITE_TRIGGERS = {
    "platform_coupon_definitions_privacy_insert": "platform_coupon_definitions",
    "platform_coupon_definitions_privacy_update": "platform_coupon_definitions",
    "platform_coupon_redemptions_capacity": "platform_coupon_redemptions",
    "platform_coupon_redemptions_privacy_insert": "platform_coupon_redemptions",
    "platform_coupon_redemptions_privacy_update": "platform_coupon_redemptions",
    "platform_entitlement_events_source_exact": "platform_entitlement_events",
    "platform_entitlement_events_privacy_insert": "platform_entitlement_events",
    "platform_entitlement_events_privacy_update": "platform_entitlement_events",
}
_COUPON_POSTGRESQL_TRIGGERS = {
    "platform_coupon_definitions_privacy_guard": (
        "platform_coupon_definitions", 23,
        "platform_coupon_definitions_privacy_guard_fn"),
    "platform_coupon_redemptions_capacity": (
        "platform_coupon_redemptions", 7,
        "platform_coupon_redemptions_capacity_fn"),
    "platform_coupon_redemptions_privacy_guard": (
        "platform_coupon_redemptions", 23,
        "platform_coupon_redemptions_privacy_guard_fn"),
    "platform_entitlement_events_source_exact": (
        "platform_entitlement_events", 7,
        "platform_entitlement_events_source_exact_fn"),
    "platform_entitlement_events_privacy_guard": (
        "platform_entitlement_events", 23,
        "platform_entitlement_events_privacy_guard_fn"),
}


def _compact_semantic_sql(value: object) -> str:
    source = str(value)
    compact: list[str] = []
    pending_space = False
    index = 0

    def append_token(token: str) -> None:
        nonlocal pending_space
        if pending_space and compact:
            compact.append(" ")
        compact.append(token)
        pending_space = False

    while index < len(source):
        character = source[index]
        if character.isspace():
            pending_space = True
            index += 1
            continue

        if character in {"'", '"'}:
            quote = character
            escaped_by_backslash = (
                quote == "'" and index > 0 and source[index - 1] in {"e", "E"}
                and (index < 2 or not (
                    source[index - 2].isalnum() or source[index - 2] in {"_", "$"}
                ))
            )
            end = index + 1
            while end < len(source):
                if escaped_by_backslash and source[end] == "\\":
                    end = min(end + 2, len(source))
                    continue
                if source[end] == quote:
                    if end + 1 < len(source) and source[end + 1] == quote:
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            append_token(source[index:end])
            index = end
            continue

        if character == "$":
            delimiter_match = re.match(
                r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", source[index:])
            if delimiter_match is not None:
                delimiter = delimiter_match.group(0)
                body_start = index + len(delimiter)
                body_end = source.find(delimiter, body_start)
                end = len(source) if body_end < 0 else body_end + len(delimiter)
                append_token(source[index:end])
                index = end
                continue

        append_token(character.lower())
        index += 1

    return "".join(compact)


def _expected_coupon_ddl(expected_tables, dialect: str) -> tuple[str, ...]:
    statements: list[str] = []
    for table_name in _COUPON_READINESS_TABLES:
        table = expected_tables[table_name]
        for ddl in table.dispatch.after_create:
            if getattr(getattr(ddl, "_ddl_if", None), "dialect", None) == dialect:
                statements.append(str(ddl.statement))
    return tuple(statements)


def _ddl_object_name(statement: str) -> str | None:
    match = re.match(
        r"\s*CREATE(?:\s+OR\s+REPLACE)?\s+(?:TRIGGER|FUNCTION)\s+([A-Za-z0-9_]+)",
        statement, flags=re.IGNORECASE)
    return None if match is None else match.group(1).lower()


def _expected_postgresql_functions(expected_tables) -> dict[str, str]:
    functions: dict[str, str] = {}
    for statement in _expected_coupon_ddl(expected_tables, "postgresql"):
        name = _ddl_object_name(statement)
        if name is None or re.match(
                r"\s*CREATE\s+OR\s+REPLACE\s+FUNCTION\b",
                statement, flags=re.IGNORECASE) is None:
            continue
        body = re.search(r"\bAS\s+\$\$(.*)\$\$\s+LANGUAGE\b", statement,
                         flags=re.IGNORECASE | re.DOTALL)
        if body is None:
            raise RuntimeError(f"coupon readiness cannot parse expected function {name}")
        functions[name] = _compact_semantic_sql(body.group(1))
    return functions


def _validate_coupon_trigger_contract(connection, expected_tables) -> None:
    dialect = connection.dialect.name
    if dialect == "sqlite":
        expected = sorted(
            (name, _COUPON_SQLITE_TRIGGERS[name],
             _compact_semantic_sql(statement))
            for statement in _expected_coupon_ddl(expected_tables, "sqlite")
            if (name := _ddl_object_name(statement)) in _COUPON_SQLITE_TRIGGERS
        )
        actual = sorted(
            (str(name), str(relation), _compact_semantic_sql(sql))
            for name, relation, sql in connection.exec_driver_sql(
                "SELECT name,tbl_name,sql FROM sqlite_master "
                "WHERE type='trigger' AND name IN "
                f"({','.join('?' for _ in _COUPON_SQLITE_TRIGGERS)})",
                tuple(_COUPON_SQLITE_TRIGGERS),
            )
        )
        if len(expected) != len(_COUPON_SQLITE_TRIGGERS) or actual != expected:
            raise RuntimeError(
                "coupon readiness SQLite trigger contract is invalid: "
                f"expected_rows={len(expected)} actual_rows={len(actual)}")
        return
    if dialect != "postgresql":
        raise RuntimeError("coupon readiness requires SQLite or PostgreSQL")
    expected_functions = _expected_postgresql_functions(expected_tables)
    rows = connection.execute(_sa_text("""
        SELECT trigger.tgname, relation.relname, trigger.tgenabled,
               trigger.tgisinternal, trigger.tgtype,
               trigger.tgqual IS NULL AS has_no_when,
               relation_namespace.nspname AS relation_schema,
               function_namespace.nspname AS function_schema,
               procedure.proname, procedure.prosrc,
               language.lanname, procedure.prosecdef
        FROM pg_trigger AS trigger
        JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
        JOIN pg_namespace AS relation_namespace ON relation_namespace.oid = relation.relnamespace
        JOIN pg_proc AS procedure ON procedure.oid = trigger.tgfoid
        JOIN pg_namespace AS function_namespace ON function_namespace.oid = procedure.pronamespace
        JOIN pg_language AS language ON language.oid = procedure.prolang
        WHERE trigger.tgname = ANY(:names)
    """), {"names": list(_COUPON_POSTGRESQL_TRIGGERS)}).mappings().all()
    expected_schema = connection.execute(_sa_text(
        "SELECT current_schema()"
    )).scalar_one()
    expected = sorted(
        (
            name, relation, expected_schema, "O", False, trigger_type, True,
            function, expected_schema, expected_functions.get(function),
            "plpgsql", False,
        )
        for name, (relation, trigger_type, function)
        in _COUPON_POSTGRESQL_TRIGGERS.items()
    )
    actual = sorted(
        (
            str(row["tgname"]), str(row["relname"]),
            str(row["relation_schema"]), str(row["tgenabled"]),
            bool(row["tgisinternal"]), int(row["tgtype"]),
            bool(row["has_no_when"]), str(row["proname"]),
            str(row["function_schema"]),
            _compact_semantic_sql(row["prosrc"]), str(row["lanname"]),
            bool(row["prosecdef"]),
        )
        for row in rows
    )
    if actual != expected:
        raise RuntimeError(
            "coupon readiness PostgreSQL trigger contract is invalid: "
            f"expected_rows={len(expected)} actual_rows={len(actual)}")


def _validate_coupon_persisted_envelopes(connection, expected_tables) -> None:
    definition = expected_tables["platform_coupon_definitions"]
    redemption = expected_tables["platform_coupon_redemptions"]
    definitions = {
        row["coupon_id"]: row
        for row in connection.execute(definition.select()).mappings()
    }
    for row in definitions.values():
        fixed = (
            row["entitlement_effect_timing"] == "FIXED_ABSOLUTE"
            and row["entitlement_valid_from"] is not None
            and row["entitlement_duration_seconds"] is None
            and (row["entitlement_valid_until"] is None
                 or row["entitlement_valid_until"] > row["entitlement_valid_from"])
        )
        dynamic = (
            row["entitlement_effect_timing"] == "DYNAMIC_DURATION"
            and row["entitlement_valid_from"] is None
            and row["entitlement_valid_until"] is None
            and row["entitlement_duration_seconds"] == 1_296_000
            and row["trial_policy_address"] is not None
            and row["discount_policy_address"] is None
            and row["entitlement_transition"] == "GRANT"
        )
        if not (fixed or dynamic):
            raise RuntimeError("coupon readiness found malformed definition envelope")
    for row in connection.execute(redemption.select()).mappings():
        source = definitions.get(row["coupon_id"])
        if source is None:
            raise RuntimeError("coupon readiness found orphan redemption")
        if source["entitlement_effect_timing"] == "DYNAMIC_DURATION":
            expected_from = row["redeemed_at"]
            expected_until = row["redeemed_at"] + dt.timedelta(seconds=1_296_000)
        else:
            expected_from = source["entitlement_valid_from"]
            expected_until = source["entitlement_valid_until"]
        if (row["policy_address"] != source["policy_address"]
                or row["entitlement_code"] != source["entitlement_code"]
                or row["entitlement_transition"] != source["entitlement_transition"]
                or row["entitlement_valid_from"] != expected_from
                or row["entitlement_valid_until"] != expected_until):
            raise RuntimeError("coupon readiness found malformed redemption envelope")


def _validate_coupon_dynamic_validity_readiness(engine: Engine, expected_tables) -> None:
    if expected_tables is None:
        expected_tables = _current_model_tables()
    subset = {name: expected_tables[name] for name in _COUPON_READINESS_TABLES}
    _validate_current_schema(engine, subset)
    table = expected_tables["platform_coupon_definitions"]
    constraint = next(
        item for item in table.constraints
        if isinstance(item, CheckConstraint)
        and item.name == "ck_platform_coupon_entitlement_shape")
    with engine.connect() as connection:
        actual_checks = {
            item["name"]: item["sqltext"]
            for item in inspect(connection).get_check_constraints(table.name)
            if item.get("name") is not None
        }
        actual = actual_checks.get(constraint.name)
        expected = _compiled_sql(constraint.sqltext, connection.dialect)
        if connection.dialect.name == "postgresql":
            validated = connection.execute(_sa_text("""
                SELECT c.convalidated
                FROM pg_constraint AS c
                JOIN pg_class AS relation ON relation.oid = c.conrelid
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = current_schema()
                  AND relation.relname = :table
                  AND c.conname = :constraint
            """), {"table": table.name, "constraint": constraint.name}).scalar_one_or_none()
            if validated is not True:
                raise RuntimeError("coupon readiness entitlement shape CHECK is not validated")
        alternatives = [expected]
        if (connection.dialect.name == "postgresql"
                and expected.startswith("(") and expected.endswith(")")
                and ")) OR (" in expected):
            alternatives.append(expected[1:-1].replace(") OR (", " OR ", 1))
        if actual is None or not any(check_sql_matches(
                table, constraint.name, connection.dialect.name,
                alternative, actual, context="coupon")
                for alternative in alternatives):
            raise RuntimeError("coupon readiness entitlement shape CHECK is invalid")
        _validate_coupon_trigger_contract(connection, expected_tables)
        _validate_coupon_persisted_envelopes(connection, expected_tables)


def _current_model_tables():
    from app.db.models import Base
    return Base.metadata.tables


def _validate_current_schema(engine: Engine, expected_tables) -> None:
    """Reject a partial current relational schema before it handles work."""
    if expected_tables is None:
        return
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    missing_tables = set(expected_tables) - actual_tables
    defects: dict[str, dict] = {}
    for table_name, table in expected_tables.items():
        if table_name not in actual_tables:
            continue
        reflected_columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        actual_columns = set(reflected_columns)
        expected_columns = set(table.columns.keys())
        actual_pk = set(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
        expected_pk = {column.name for column in table.primary_key.columns}
        actual_fks = {
            (tuple(fk["constrained_columns"]), fk["referred_table"],
             tuple(fk["referred_columns"]),
             (fk.get("options") or {}).get("ondelete"),
             (fk.get("options") or {}).get("onupdate"))
            for fk in inspector.get_foreign_keys(table_name)
        }
        expected_fks = {
            (tuple(element.parent.name for element in constraint.elements),
             constraint.elements[0].column.table.name,
             tuple(element.column.name for element in constraint.elements),
             constraint.ondelete, constraint.onupdate)
            for constraint in table.foreign_key_constraints
        }
        actual_uniques = {
            tuple(unique["column_names"])
            for unique in inspector.get_unique_constraints(table_name)
        }
        expected_uniques = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        actual_checks = {
            check["name"]
            for check in inspector.get_check_constraints(table_name)
            if check["name"] is not None
        }
        expected_checks = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
            and constraint.name is not None
        }
        actual_indexes = {
            index["name"]: (
                tuple(index["column_names"]), bool(index.get("unique")),
                (index.get("dialect_options") or {}).get(
                    f"{engine.dialect.name}_where") is not None,
            )
            for index in inspector.get_indexes(table_name)
        }
        expected_indexes = {
            index.name: (
                tuple(column.name for column in index.columns), bool(index.unique),
                index.dialect_options[engine.dialect.name].get("where") is not None,
            )
            for index in table.indexes
        }
        table_defects = {}
        if expected_columns - actual_columns:
            table_defects["missing_columns"] = sorted(expected_columns - actual_columns)
        if actual_columns - expected_columns:
            table_defects["unexpected_columns"] = sorted(actual_columns - expected_columns)
        column_defects = {}
        for column in table.columns:
            reflected = reflected_columns.get(column.name)
            if reflected is None:
                continue
            expected = {
                "nullable": bool(column.nullable),
                "default": _normalize_default(_compiled_sql(
                    column.server_default.arg if column.server_default is not None else None,
                    engine.dialect)),
            }
            actual = {
                "nullable": bool(reflected["nullable"]),
                "default": _normalize_default(reflected.get("default")),
            }
            if (not _types_are_compatible(column.type, reflected["type"])
                    or actual["nullable"] != expected["nullable"]
                    or not _defaults_are_equivalent(
                        column, expected["default"], actual["default"],
                        engine.dialect.name)):
                column_defects[column.name] = {
                    "expected": {**expected, "type": str(column.type)},
                    "actual": {**actual, "type": str(reflected["type"])},
                }
        if column_defects:
            table_defects["columns"] = column_defects
        if actual_pk != expected_pk:
            table_defects["primary_key"] = {"expected": sorted(expected_pk),
                                             "actual": sorted(actual_pk)}
        if not expected_fks.issubset(actual_fks):
            table_defects["missing_foreign_keys"] = sorted(expected_fks - actual_fks)
        if expected_uniques != actual_uniques:
            table_defects["unique_constraints"] = {"expected": expected_uniques,
                                                    "actual": actual_uniques}
        if expected_checks != actual_checks:
            table_defects["check_constraints"] = {
                "expected": expected_checks, "actual": actual_checks,
            }
        mismatched_indexes = {
            name: {"expected": expected, "actual": actual_indexes.get(name)}
            for name, expected in expected_indexes.items()
            if actual_indexes.get(name) != expected
        }
        if mismatched_indexes:
            table_defects["indexes"] = mismatched_indexes
        if table_defects:
            defects[table_name] = table_defects
    if missing_tables or defects:
        raise RuntimeError(
            "Database schema is not the current execution relational model: "
            f"missing_tables={sorted(missing_tables)} defects={defects}"
        )


def _validate_postgresql_startup(engine, expected_tables, *, coupon):
    _validate_current_schema(engine, expected_tables)
    _validate_postgresql_immutable_triggers(engine)
    if coupon:
        _validate_coupon_dynamic_validity_readiness(engine, expected_tables)


def _init_managed_postgresql(engine, current, expected_tables):
    # Preserve only the historical transitions already accepted by this runner.
    if (current, head_revision()) in {("0048", "0049"), ("0049", "0050"), ("0051", "0052"), ("0052", "0053"), ("0053", "0054"), ("0054", "0055"), ("0054", "0056"), ("0055", "0056")}:
        upgraded = upgrade_to_head(engine)
        _validate_postgresql_startup(engine, expected_tables, coupon=True)
        return upgraded
    if current != head_revision():
        raise RuntimeError(
            "PostgreSQL schema is not at head; historical SQLite migrations "
            "are not replayed against PostgreSQL")
    _validate_postgresql_startup(engine, expected_tables, coupon=current == "0049")
    return current


def _init_postgresql(engine, current, create_all, expected_tables):
    if current is not None:
        return _init_managed_postgresql(engine, current, expected_tables)
    if _has_tables(engine):
        raise RuntimeError(
            "Refusing populated unmanaged PostgreSQL database: use the verified "
            "SQLite-to-PostgreSQL cutover path instead of adopting or replaying it")
    create_all()
    _validate_postgresql_startup(engine, expected_tables, coupon=True)
    stamp(engine, head_revision())
    return schema_version(engine)


def _init_managed_sqlite(engine, current, expected_tables):
    # Same-head startup stays read-only and never opens an Alembic write transaction.
    result = current if current == head_revision() else upgrade_to_head(engine)
    if result == "0049":
        _validate_coupon_dynamic_validity_readiness(engine, expected_tables)
    return result


def _adopt_unmanaged_sqlite(engine, legacy_migrate):
    # Frozen baseline adoption is distinct from a managed stale-head upgrade.
    legacy_migrate()
    _create_baseline_tables(engine)
    stamp(engine, BASELINE_REVISION)
    target = "0054" if head_revision() in {"0055", "0056"} else "head"
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), target)
    return upgrade_to_head(engine) if target == "0054" else schema_version(engine)


def init_schema(engine: Engine, *, create_all, legacy_migrate, expected_tables=None) -> str | None:
    """Initialize the existing database according to its dialect and managed state."""
    current = schema_version(engine)
    if _is_postgresql(engine):
        return _init_postgresql(engine, current, create_all, expected_tables)
    if current is not None:
        return _init_managed_sqlite(engine, current, expected_tables)
    if _has_tables(engine):
        return _adopt_unmanaged_sqlite(engine, legacy_migrate)
    create_all()
    _validate_coupon_dynamic_validity_readiness(engine, expected_tables)
    stamp(engine, head_revision())
    return schema_version(engine)


def _main(argv: list[str] | None = None) -> int:
    import argparse

    from app.db.session import engine as app_engine

    p = argparse.ArgumentParser(
        prog="python -m app.db.migrate",
        description="Execution-database migrations. Operates on PT_DB_PATH.")
    p.add_argument("action", choices=["current", "head", "upgrade", "history"],
                   help="current: what this DB is stamped at · head: what this build "
                        "expects · upgrade: apply pending revisions · history: list them")
    args = p.parse_args(argv)

    if args.action == "current":
        print(schema_version(app_engine) or "(unmanaged — no alembic_version table)")
    elif args.action == "head":
        print(head_revision())
    elif args.action == "upgrade":
        before = schema_version(app_engine)
        after = upgrade_to_head(app_engine)
        print(f"{before or '(unmanaged)'} -> {after}")
    else:
        command.history(alembic_config(), verbose=True)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(_main())
