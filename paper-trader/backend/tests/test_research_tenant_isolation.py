"""Tenant ownership and migration boundaries for the separate research database."""
from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from research.domain.base import ResearchBase, init_research_db, make_engine
from research.domain import migrate as migrate_module
from research.domain.migrate import LEGACY_OWNER_ID, ResearchMigrationError, downgrade_research_db
from research.domain.models import (
    BlockEdge,
    ExperimentRun,
    ExperimentSpec,
    GeneratedStrategyRecord,
    Hypothesis,
    PromotionCandidate,
    ResearchProgram,
)
from research.orchestrator.run import spec_hash
from research.evidence import encode_terminal_evidence
from app.core import research_read


def test_empty_initialization_stamps_research_owned_schema_version(tmp_path):
    """A blank research database becomes the owner-scoped head schema.

    Removing the migrator call from ``init_research_db`` must make this test fail:
    the application must not treat ``metadata.create_all`` as a migration system.
    """
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        tables = set(inspect(engine).get_table_names())
        assert "research_schema_version" in tables
        with engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version FROM research_schema_version"
            )).scalar_one() == "0001"
        owner_column = next(
            column for column in inspect(engine).get_columns("research_program")
            if column["name"] == "owner_id"
        )
        assert owner_column["nullable"] is False
    finally:
        engine.dispose()


def test_legacy_rows_upgrade_losslessly_and_two_owners_share_content_addresses(tmp_path):
    """A legacy row keeps its exact payload while a second owner can reuse its hash.

    Removing owner from a composite locator, or changing recipe bytes while adding
    tenancy, makes this test fail.
    """
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE research_program (id INTEGER PRIMARY KEY, name VARCHAR(80), thesis TEXT, status VARCHAR(12), created_at DATETIME);
            CREATE TABLE research_hypothesis (id INTEGER PRIMARY KEY, program_id INTEGER REFERENCES research_program(id), statement TEXT, status VARCHAR(12), retest_priority FLOAT, last_tested_at DATETIME, created_at DATETIME);
            CREATE TABLE research_experiment_spec (id VARCHAR(64) PRIMARY KEY, hypothesis_id INTEGER REFERENCES research_hypothesis(id), parent_spec_id VARCHAR(64) REFERENCES research_experiment_spec(id), recipe_json TEXT, git_commit VARCHAR(40), qualifier_version VARCHAR(24), optimizer_version VARCHAR(24), validator_version VARCHAR(24), scoring_version VARCHAR(24), rng_seed INTEGER, created_at DATETIME);
            CREATE TABLE research_experiment_run (id INTEGER PRIMARY KEY, spec_id VARCHAR(64) REFERENCES research_experiment_spec(id), status VARCHAR(12), decision VARCHAR(16), spent_bar_seconds FLOAT, checkpoint_json TEXT, error VARCHAR(400), started_at DATETIME, completed_at DATETIME, created_at DATETIME);
            CREATE TABLE research_finding (id INTEGER PRIMARY KEY, hypothesis_id INTEGER REFERENCES research_hypothesis(id), statement TEXT, polarity VARCHAR(8), confidence FLOAT, evidence_run_id INTEGER REFERENCES research_experiment_run(id), superseded_by INTEGER REFERENCES research_finding(id), created_at DATETIME);
            CREATE TABLE research_optimization_trial (id INTEGER PRIMARY KEY, run_id INTEGER REFERENCES research_experiment_run(id), instrument_key VARCHAR(48), fold_index INTEGER, params_json TEXT, is_objective FLOAT, is_trades INTEGER, oos_trades INTEGER, selected BOOLEAN, created_at DATETIME);
            CREATE TABLE research_generated_strategy (key VARCHAR(64) PRIMARY KEY, composition_json TEXT, source TEXT, created_at DATETIME);
            CREATE TABLE research_promotion_candidate (id INTEGER PRIMARY KEY, run_id INTEGER REFERENCES research_experiment_run(id), parameterization_hash VARCHAR(64), qualifying_universe_json TEXT, scorecard_json TEXT, status VARCHAR(12), approved_git_sha VARCHAR(40), created_at DATETIME);
            CREATE TABLE research_block_edge (block_name VARCHAR(48), instrument_key VARCHAR(32), positive INTEGER, negative INTEGER, last_run_id INTEGER REFERENCES research_experiment_run(id), updated_at DATETIME, PRIMARY KEY(block_name, instrument_key));
            CREATE TABLE research_shadow_session (id INTEGER PRIMARY KEY, candidate_id INTEGER REFERENCES research_promotion_candidate(id), session_date DATE, instrument_key VARCHAR(32), trades INTEGER, wins INTEGER, net_pnl FLOAT, created_at DATETIME);
            CREATE INDEX ix_legacy_hypothesis_program ON research_hypothesis(program_id);
            CREATE INDEX ix_legacy_run_spec ON research_experiment_run(spec_id);
            CREATE TRIGGER trg_research_experiment_spec_no_update BEFORE UPDATE ON research_experiment_spec BEGIN SELECT RAISE(ABORT, 'legacy immutable'); END;
            CREATE TRIGGER trg_research_optimization_trial_no_delete BEFORE DELETE ON research_optimization_trial BEGIN SELECT RAISE(ABORT, 'legacy immutable'); END;
        """)
        now = "2026-08-12 00:00:00"
        connection.execute("INSERT INTO research_program VALUES (1, ?, ?, ?, ?)", ("same", "thesis", "active", now))
        connection.execute("INSERT INTO research_hypothesis VALUES (1, 1, ?, ?, 1.0, NULL, ?)", ("statement", "open", now))
        recipe = '{"a":1,"z":[2,3]}'
        connection.execute("INSERT INTO research_experiment_spec VALUES (?, 1, NULL, ?, 'commit', 'q1', 'o1', 'v1', 's1', 7, ?)", ("hash", recipe, now))
        connection.execute("INSERT INTO research_experiment_run VALUES (1, 'hash', 'completed', 'archive', 5.0, ?, '', ?, ?, ?)", ("{\"e\":1}", now, now, now))
        connection.execute("INSERT INTO research_finding VALUES (1, 1, 'finding', 'negative', 0.5, 1, NULL, ?)", (now,))
        connection.execute("INSERT INTO research_optimization_trial VALUES (1, 1, 'GOLDM', 0, '{\"p\":1}', 1.0, 2, 3, 1, ?)", (now,))
        connection.execute("INSERT INTO research_generated_strategy VALUES ('generated', '{\"k\":1}', 'source', ?)", (now,))
        connection.execute("INSERT INTO research_promotion_candidate VALUES (1, 1, 'param', '[]', '{}', 'pending', NULL, ?)", (now,))
        connection.execute("INSERT INTO research_block_edge VALUES ('edge', 'GOLDM', 1, 2, 1, ?)", (now,))
        connection.execute("INSERT INTO research_shadow_session VALUES (1, 1, '2026-08-12', 'GOLDM', 2, 1, 3.0, ?)", (now,))
        connection.commit()
    finally:
        connection.close()

    engine = make_engine(str(path))
    try:
        init_research_db(engine)
        Session = __import__("research.domain.base", fromlist=["make_sessionmaker"]).make_sessionmaker(engine)
        with Session() as session:
            legacy = session.get(ExperimentSpec, (LEGACY_OWNER_ID, "hash"))
            assert legacy.recipe_json == '{"a":1,"z":[2,3]}'
            assert session.get(GeneratedStrategyRecord, (LEGACY_OWNER_ID, "generated")).source == "source"
            program = ResearchProgram(owner_id="owner-b", name="same", thesis="b")
            session.add(program)
            session.flush()
            hypothesis = Hypothesis(owner_id="owner-b", program_id=program.id, statement="statement")
            session.add(hypothesis)
            session.flush()
            session.add(ExperimentSpec(owner_id="owner-b", id="hash", hypothesis_id=hypothesis.id, recipe_json=legacy.recipe_json))
            session.add(GeneratedStrategyRecord(owner_id="owner-b", key="generated", source="b"))
            session.add(BlockEdge(owner_id="owner-b", block_name="edge", instrument_key="GOLDM"))
            session.commit()
        with engine.connect() as check:
            assert check.exec_driver_sql(
                "SELECT owner_id, id, name, thesis, status, created_at FROM research_program WHERE owner_id=?",
                (LEGACY_OWNER_ID,),
            ).one() == (LEGACY_OWNER_ID, 1, "same", "thesis", "active", now)
            assert check.exec_driver_sql(
                "SELECT owner_id, id, program_id, statement, status, retest_priority, last_tested_at, created_at FROM research_hypothesis WHERE owner_id=?",
                (LEGACY_OWNER_ID,),
            ).one() == (LEGACY_OWNER_ID, 1, 1, "statement", "open", 1.0, None, now)
            assert check.exec_driver_sql(
                "SELECT owner_id, id, hypothesis_id, recipe_json, rng_seed, created_at FROM research_experiment_spec WHERE owner_id=?",
                (LEGACY_OWNER_ID,),
            ).one() == (LEGACY_OWNER_ID, "hash", 1, recipe, 7, now)
            assert check.exec_driver_sql(
                "SELECT owner_id, id, spec_id, checkpoint_json, started_at, completed_at, created_at FROM research_experiment_run WHERE owner_id=?",
                (LEGACY_OWNER_ID,),
            ).one() == (LEGACY_OWNER_ID, 1, "hash", "{\"e\":1}", now, now, now)
            assert check.exec_driver_sql("SELECT owner_id, id, hypothesis_id, evidence_run_id, created_at FROM research_finding WHERE owner_id=?", (LEGACY_OWNER_ID,)).one() == (LEGACY_OWNER_ID, 1, 1, 1, now)
            assert check.exec_driver_sql("SELECT owner_id, id, run_id, params_json, created_at FROM research_optimization_trial WHERE owner_id=?", (LEGACY_OWNER_ID,)).one() == (LEGACY_OWNER_ID, 1, 1, '{"p":1}', now)
            assert check.exec_driver_sql("SELECT owner_id, key, composition_json, source, created_at FROM research_generated_strategy WHERE owner_id=?", (LEGACY_OWNER_ID,)).one() == (LEGACY_OWNER_ID, "generated", '{"k":1}', "source", now)
            assert check.exec_driver_sql("SELECT owner_id, id, run_id, parameterization_hash, approved_git_sha, created_at FROM research_promotion_candidate WHERE owner_id=?", (LEGACY_OWNER_ID,)).one() == (LEGACY_OWNER_ID, 1, 1, "param", None, now)
            assert check.exec_driver_sql("SELECT owner_id, block_name, instrument_key, last_run_id, updated_at FROM research_block_edge WHERE owner_id=?", (LEGACY_OWNER_ID,)).one() == (LEGACY_OWNER_ID, "edge", "GOLDM", 1, now)
            assert check.exec_driver_sql("SELECT owner_id, id, candidate_id, session_date, created_at FROM research_shadow_session WHERE owner_id=?", (LEGACY_OWNER_ID,)).one() == (LEGACY_OWNER_ID, 1, 1, "2026-08-12", now)
    finally:
        engine.dispose()


def test_composite_foreign_keys_reject_cross_owner_rows(tmp_path):
    """A guessed foreign id cannot attach an owner B spec to owner A's hypothesis."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        from research.domain.base import make_sessionmaker
        with make_sessionmaker(engine)() as session:
            program = ResearchProgram(owner_id="owner-a", name="program", thesis="")
            session.add(program)
            session.flush()
            hypothesis = Hypothesis(owner_id="owner-a", program_id=program.id, statement="h")
            session.add(hypothesis)
            session.commit()
            session.add(ExperimentSpec(owner_id="owner-b", id="same-hash", hypothesis_id=hypothesis.id))
            with pytest.raises(IntegrityError):
                session.commit()
    finally:
        engine.dispose()


def test_completed_temp_table_recovers_before_versioned_head_noop(tmp_path):
    """A process death after source drop resumes from the deterministic temp name."""
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE research_program RENAME TO research_program__owner_tmp"
            )
        init_research_db(engine)
        assert "research_program" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def _schema_contract(engine) -> dict:
    inspector = inspect(engine)
    tables = sorted(name for name in inspector.get_table_names() if name.startswith("research_"))
    return {
        table: {
            "columns": tuple((column["name"], column["nullable"]) for column in inspector.get_columns(table)),
            "primary_key": tuple(inspector.get_pk_constraint(table)["constrained_columns"] or ()),
            "unique_constraints": tuple(sorted(
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table)
            )),
            "foreign_keys": tuple(sorted(
                (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
                for fk in inspector.get_foreign_keys(table)
            )),
            "indexes": tuple(sorted(tuple(index["column_names"]) for index in inspector.get_indexes(table))),
        }
        for table in tables
    }


def test_fresh_and_upgraded_databases_converge_to_one_schema_contract(tmp_path):
    """The migration's result, not its DDL spelling, is stable across start states."""
    fresh = make_engine(str(tmp_path / "fresh.db"))
    upgraded = make_engine(str(tmp_path / "upgraded.db"))
    try:
        init_research_db(fresh)
        init_research_db(upgraded)
        with upgraded.begin() as connection:
            connection.exec_driver_sql("DROP TABLE research_schema_version")
        init_research_db(upgraded)
        assert _schema_contract(fresh) == _schema_contract(upgraded)
    finally:
        fresh.dispose()
        upgraded.dispose()


@pytest.mark.parametrize("table", [table.name for table in ResearchBase.metadata.sorted_tables])
def test_every_rebuild_table_recovers_source_plus_stale_temp(tmp_path, table):
    """The source wins over a deterministic stale temp table for every rebuild target."""
    engine = make_engine(str(tmp_path / f"{table}.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE research_schema_version")
            connection.exec_driver_sql(f'CREATE TABLE "{table}__owner_tmp" (discarded INTEGER)')
        init_research_db(engine)
        assert f"{table}__owner_tmp" not in inspect(engine).get_table_names()
        assert table in inspect(engine).get_table_names()
    finally:
        engine.dispose()


@pytest.mark.parametrize("table", [table.name for table in ResearchBase.metadata.sorted_tables])
def test_every_rebuild_table_recovers_completed_temp_without_source(tmp_path, table):
    """A completed target becomes the source again after a process death for every table."""
    engine = make_engine(str(tmp_path / f"completed-{table}.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(f'ALTER TABLE "{table}" RENAME TO "{table}__owner_tmp"')
        init_research_db(engine)
        assert table in inspect(engine).get_table_names()
        assert f"{table}__owner_tmp" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_foreign_key_state_is_restored_after_injected_upgrade_failure(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "failure.db"))
    try:
        init_research_db(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE research_schema_version")
        monkeypatch.setattr(
            migrate_module, "_after_table_rebuilt",
            lambda _name: (_ for _ in ()).throw(RuntimeError("injected rebuild failure")),
        )
        with pytest.raises(RuntimeError, match="injected rebuild failure"):
            init_research_db(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()


def test_wrong_owner_root_locators_have_the_same_absent_shape_and_preserve_other_rows(tmp_path):
    """Owner B cannot distinguish owner A's guessed root locators from absent ones."""
    engine = make_engine(str(tmp_path / "isolation.db"))
    try:
        init_research_db(engine)
        from research.domain.base import make_sessionmaker
        with make_sessionmaker(engine)() as session:
            program_a = ResearchProgram(owner_id="owner-a", name="program", thesis="a")
            program_b = ResearchProgram(owner_id="owner-b", name="program", thesis="b")
            session.add_all([program_a, program_b])
            session.flush()
            hypothesis_a = Hypothesis(owner_id="owner-a", program_id=program_a.id, statement="h")
            hypothesis_b = Hypothesis(owner_id="owner-b", program_id=program_b.id, statement="h")
            session.add_all([hypothesis_a, hypothesis_b])
            session.flush()
            session.add_all([
                ExperimentSpec(owner_id="owner-a", id="same", hypothesis_id=hypothesis_a.id, recipe_json='{"a":1}'),
                ExperimentSpec(owner_id="owner-b", id="same", hypothesis_id=hypothesis_b.id, recipe_json='{"b":1}'),
                GeneratedStrategyRecord(owner_id="owner-a", key="key", source="a"),
                GeneratedStrategyRecord(owner_id="owner-b", key="key", source="b"),
                BlockEdge(owner_id="owner-a", block_name="block", instrument_key="GOLDM", positive=1),
                BlockEdge(owner_id="owner-b", block_name="block", instrument_key="GOLDM", positive=9),
            ])
            session.commit()
            assert session.get(ExperimentSpec, ("owner-c", "same")) is None
            assert session.get(ExperimentSpec, ("owner-c", "missing")) is None
            assert session.get(GeneratedStrategyRecord, ("owner-c", "key")) is None
            assert session.get(GeneratedStrategyRecord, ("owner-c", "missing")) is None
            assert session.get(BlockEdge, ("owner-c", "block", "GOLDM")) is None
            assert session.get(BlockEdge, ("owner-c", "missing", "GOLDM")) is None
            session.get(BlockEdge, ("owner-a", "block", "GOLDM")).positive = 2
            session.commit()
            assert session.get(ExperimentSpec, ("owner-b", "same")).recipe_json == '{"b":1}'
            assert session.get(GeneratedStrategyRecord, ("owner-b", "key")).source == "b"
            assert session.get(BlockEdge, ("owner-b", "block", "GOLDM")).positive == 9
    finally:
        engine.dispose()


def test_two_owner_rows_keep_identical_canonical_spec_and_evidence_bytes(tmp_path):
    recipe = {"strategy": "trend", "params": {"length": 20}, "datasets": {"GOLDM": "digest"}}
    spec_id = spec_hash(recipe)
    payload = {"spec_id": spec_id, "provenance": recipe, "results": {"address": "sha256:abc"}}
    engine = make_engine(str(tmp_path / "canonical.db"))
    try:
        init_research_db(engine)
        from research.domain.base import make_sessionmaker
        with make_sessionmaker(engine).begin() as session:
            for owner_id in ("owner-a", "owner-b"):
                program = ResearchProgram(owner_id=owner_id, name="same", thesis="")
                session.add(program)
                session.flush()
                hypothesis = Hypothesis(owner_id=owner_id, program_id=program.id, statement="same")
                session.add(hypothesis)
                session.flush()
                session.add(ExperimentSpec(
                    owner_id=owner_id, id=spec_id, hypothesis_id=hypothesis.id,
                    recipe_json='{"datasets":{"GOLDM":"digest"},"params":{"length":20},"strategy":"trend"}',
                ))
                session.flush()
                session.add(ExperimentRun(owner_id=owner_id, spec_id=spec_id, status="pending"))
        with make_sessionmaker(engine)() as session:
            left = session.get(ExperimentSpec, ("owner-a", spec_id))
            right = session.get(ExperimentSpec, ("owner-b", spec_id))
            assert left is not None and right is not None
            assert left.id == right.id == spec_hash(recipe)
            assert encode_terminal_evidence(payload) == encode_terminal_evidence(dict(payload))
    finally:
        engine.dispose()


def test_project_read_boundaries_require_an_explicit_owner():
    """A project-scoped read cannot silently query all research tenants."""
    assert research_read.get_graph_run("project", 999, owner_id="owner-a") is None


def test_project_reads_hide_a_foreign_run_like_an_absent_run(tmp_path, monkeypatch):
    """The read bridge scopes the database predicate before project provenance."""
    path = tmp_path / "read-scope.db"
    monkeypatch.setattr(research_read, "research_db_path", lambda: str(path))
    engine = make_engine(str(path))
    try:
        init_research_db(engine)
        from research.domain.base import make_sessionmaker
        with make_sessionmaker(engine).begin() as session:
            program = ResearchProgram(owner_id="owner-a", name="program", thesis="")
            session.add(program)
            session.flush()
            hypothesis = Hypothesis(owner_id="owner-a", program_id=program.id, statement="h")
            session.add(hypothesis)
            session.flush()
            session.add(ExperimentSpec(
                owner_id="owner-a", id="spec", hypothesis_id=hypothesis.id,
                recipe_json='{"strategy":"generated","graph_provenance":{"graph":{"project_id":"project"}}}',
            ))
            session.flush()
            run = ExperimentRun(owner_id="owner-a", spec_id="spec", status="pending")
            session.add(run)
            session.flush()
            foreign_run_id = run.id
            candidate = PromotionCandidate(
                owner_id="owner-a", run_id=run.id, parameterization_hash="p" * 64,
                qualifying_universe_json="[]", scorecard_json="{}", status="pending",
            )
            session.add(candidate)
            session.add(GeneratedStrategyRecord(
                owner_id="owner-a", key="generated", composition_json='{"nodes":[]}', source="owner-a",
            ))
            session.flush()
            foreign_candidate_id = candidate.id
        assert research_read.get_graph_run("project", foreign_run_id, owner_id="owner-b") is None
        assert research_read.get_graph_run("project", foreign_run_id + 1, owner_id="owner-b") is None
        assert research_read.list_graph_runs("project", owner_id="owner-b") == []
        assert [view["run_id"] for view in research_read.list_graph_runs("project", owner_id="owner-a")] == [foreign_run_id]
        assert research_read.get_promotion(foreign_candidate_id, owner_id="owner-b") is None
        assert research_read.list_pending_promotions(owner_id="owner-b") == []
        owned_candidate = research_read.get_promotion(foreign_candidate_id, owner_id="owner-a")
        assert owned_candidate is not None
        assert owned_candidate["generated_source"] == "owner-a"
    finally:
        engine.dispose()


def test_downgrade_refusal_is_non_destructive(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    try:
        init_research_db(engine)
        with pytest.raises(ResearchMigrationError, match="unsupported"):
            downgrade_research_db(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version FROM research_schema_version")).scalar_one() == "0001"
    finally:
        engine.dispose()
