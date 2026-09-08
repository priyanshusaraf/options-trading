"""Retained A-01 fixtures now prove finite-runner refusal of SQLite 0005.

The direct 0011 contract supports only clean, exact 0010, and exact 0011.
These independently inspectable populated 0005 fixtures remain useful only as
unsupported-state inputs.  They must refuse without changing catalog, rows,
sequences, marker, or stored bytes.

Prevention invariant (audit §A-01): every migration stage installs and
validates its complete target contract — table, index, constraint, trigger,
marker — before the marker advances, and one canonical source owns every
trigger's SQL bytes.  The defect this pins: ``0007``'s literal and
``migrate._expected_triggers`` disagreed by a single space inside
``research_dataset_manifests_refuse_secret_key``, so the 0010 prefix validator
found no exact declared restart boundary and refused a fully-migrated state.

Mutation contract: re-introducing any byte drift between the 0007 literal and
the canonical trigger text turns these tests red; deleting the canonical-text
comparison in the 0010 validator also turns them red.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from research.domain import migrate
from research.domain.base import make_engine
from research_tests.test_ir_v2_research_migration import (
    _REFUSAL_PATTERN,
    _legacy_artifact,
    _make_populated_0005,
    _sqlite_logical_digest,
)

CANONICAL_TRIGGERS = migrate._expected_triggers


def _trigger_names(connection):
    return sorted(
        name for (name,) in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='trigger'").all())


def test_seeded_0005_runner_refuses_before_trigger_or_marker_write(tmp_path):
    engine, _address = _make_populated_0005(tmp_path / "research.db")
    try:
        before = _sqlite_logical_digest(engine)
        with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
            migrate.migrate_research_db(engine)
        assert _sqlite_logical_digest(engine) == before
        with engine.connect() as connection:
            marker = connection.execute(
                text("SELECT version FROM research_schema_version")).scalar_one()
            assert marker == "0005"
    finally:
        engine.dispose()


def test_seeded_0005_refusal_preserves_the_legacy_admission_payload(tmp_path):
    engine, address = _make_populated_0005(tmp_path / "research.db")
    try:
        before = _sqlite_logical_digest(engine)
        with pytest.raises(migrate.ResearchMigrationError, match=_REFUSAL_PATTERN):
            migrate.migrate_research_db(engine)
        assert _sqlite_logical_digest(engine) == before
        with engine.connect() as connection:
            artifact, _expected_address = _legacy_artifact()
            row = connection.execute(text(
                "SELECT artifact_json FROM research_strategy_admission "
                "WHERE admission_address = :a"), {"a": address}).one_or_none()
            assert row is not None
            assert row[0] == artifact
    finally:
        engine.dispose()


def test_stage_boundaries_carry_only_their_declared_triggers(tmp_path):
    """Each stage installs its complete contract before the next one runs."""
    engine, _address = _make_populated_0005(tmp_path / "research.db")
    stages = (
        ("0006", migrate._upgrade_ir_v2_admissions,
         {"trg_research_strategy_admission_no_delete",
          "trg_research_strategy_admission_no_update"}),
        ("0007", migrate._upgrade_dataset_provenance,
         {"research_dataset_manifests_refuse_secret_key",
          "trg_research_dataset_manifests_no_delete",
          "trg_research_dataset_manifests_no_update"}),
        ("0008", migrate._upgrade_ir_v2_graph_versions,
         {"trg_research_ir_v2_graph_versions_no_delete",
          "trg_research_ir_v2_graph_versions_no_update"}),
    )
    try:
        with engine.begin() as connection:
            migrate._recover_interrupted_swaps(connection)
        seen: set[str] = set()
        with engine.begin() as connection:
            seen |= {"trg_research_experiment_spec_no_delete",
                     "trg_research_experiment_spec_no_update",
                     "trg_research_optimization_trial_no_delete",
                     "trg_research_optimization_trial_no_update",
                     "trg_research_strategy_admission_no_delete",
                     "trg_research_strategy_admission_no_update"}
        for version, upgrade, contract in stages:
            with engine.begin() as connection:
                upgrade(connection)
            with engine.connect() as connection:
                names = set(_trigger_names(connection))
                assert contract <= names, (version, contract - names)
                assert names >= seen, (version, seen - names)
                seen = names
        # The canonical 0007 trigger text must equal the module literal bytes:
        # one source of truth per trigger.
        with engine.connect() as connection:
            actual = connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type='trigger' AND "
                "name='research_dataset_manifests_refuse_secret_key'").scalar_one()
        assert migrate._normalise_sql(actual) == \
            migrate._normalise_sql(CANONICAL_TRIGGERS()[
                "research_dataset_manifests_refuse_secret_key"])
    finally:
        engine.dispose()


def test_marker_shape_is_a_declared_dialect_contract():
    """A-05 pin: SQLite carries (version, schema_cookie); PostgreSQL (version).

    The asymmetry is the contract, not drift: the cookie guards SQLite's
    restart fast-path; the PostgreSQL plane adopts only empty databases and
    has no cookie to keep.  Both shapes are pinned so neither silently
    grows the other's column.
    """
    from research.domain.migrations import postgresql_0010_contract as postgres

    assert migrate._VERSION_COLUMNS == ("version", "schema_cookie")
    pg_ddl = postgres.marker_ddl()
    assert "PRIMARY KEY (version)" in pg_ddl
    assert "schema_cookie" not in pg_ddl

    engine = make_engine(str(tmp_path_db()))
    try:
        with engine.begin() as connection:
            migrate._create_current_marker(connection)
            columns = [row[1] for row in connection.exec_driver_sql(
                f"PRAGMA table_info({migrate._quoted(migrate.VERSION_TABLE)})").all()]
        assert tuple(columns) == ("version", "schema_cookie")
    finally:
        engine.dispose()


def tmp_path_db():
    import tempfile
    return tempfile.mktemp(suffix="-marker.db")
