from __future__ import annotations

import datetime as dt
from pathlib import Path
import shutil
import subprocess

import pytest
import sqlalchemy as sa
from sqlalchemy import update
from sqlalchemy.orm import Session
from alembic import command

from app.chart.annotation_context import MarketContextIdentity
from app.chart.annotation_geometry import CausalApplicability, Level
from app.chart.annotation_repository import create_annotation
from app.db import copy_contract, restore_contract
from app.db import migrate
from app.db.models import Base, ChartContextAnnotation, Organization
from app.db.session import SessionLocal, init_db

UTC = dt.timezone.utc


def address(digit: str) -> str:
    return "sha256:" + digit * 64


def identity() -> MarketContextIdentity:
    return MarketContextIdentity("owner.restore", address("a"), {}, address("b"),
        address("c"), "XNSE · EQUITY · SPOT", 60,
        dt.datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def seed() -> dict:
    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id="owner.restore", name="Restore"))
    geometry = Level("100")
    applicability = CausalApplicability(
        dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 1, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 2, tzinfo=UTC))
    return create_annotation(identity(), geometry.canonical_bytes.decode(),
                             applicability.canonical_bytes.decode())


def fill_annotation_group(session: Session, source: ChartContextAnnotation,
                          *, total: int = 257) -> None:
    for index in range(2, total + 1):
        session.add(ChartContextAnnotation(
            owner_id=source.owner_id, market_context_address=source.market_context_address,
            annotation_id=f"00000000-0000-0000-0000-{index:012d}", revision=1,
            dataset_manifest_address=source.dataset_manifest_address,
            canonical_instrument_address=source.canonical_instrument_address,
            timeframe_seconds=source.timeframe_seconds,
            geometry_address=source.geometry_address, geometry_json=source.geometry_json,
            applicability_address=source.applicability_address,
            applicability_json=source.applicability_json,
            created_at=source.created_at, updated_at=source.updated_at))


def test_execution_copy_and_restore_inventory_include_annotation_rows():
    seed()
    with SessionLocal() as session:
        connection = session.connection()
        copy_contract._validate_content_addresses(connection, Base.metadata)
        state = restore_contract._state_counts(connection, Base.metadata)
        content = restore_contract._content_summary(connection, Base.metadata)
    assert state["chart_context_annotations"] == {"rows": 1, "max_revision": 1}
    item = next(row for row in content if row["table"] == "chart_context_annotations")
    assert item["count"] == 1 and len(item["set_digest"]) == 64


def test_copy_refuses_corrupt_annotation_without_mutating_the_row():
    created = seed()
    changed = Level("101").canonical_bytes.decode()
    with SessionLocal.begin() as session:
        session.execute(update(ChartContextAnnotation).where(
            ChartContextAnnotation.annotation_id == created["annotation_id"]
        ).values(geometry_json=changed))
    with SessionLocal() as session:
        connection = session.connection()
        with pytest.raises(copy_contract.CopyRefusal, match="chart annotation"):
            copy_contract._validate_content_addresses(connection, Base.metadata)
    with SessionLocal() as session:
        row = session.get(ChartContextAnnotation,
            (identity().owner_id, identity().market_context_address, created["annotation_id"]))
        assert row.geometry_json == changed and row.revision == 1


def test_sqlite_copy_validation_refuses_257_valid_rows_without_mutation():
    created = seed()
    with SessionLocal.begin() as session:
        source = session.get(ChartContextAnnotation,
            (identity().owner_id, identity().market_context_address, created["annotation_id"]))
        fill_annotation_group(session, source=source)
    with SessionLocal() as session:
        with pytest.raises(copy_contract.CopyRefusal, match="presentation ceiling"):
            copy_contract._validate_content_addresses(session.connection(), Base.metadata)
    with SessionLocal() as session:
        assert session.query(ChartContextAnnotation).count() == 257


def test_configured_execution_plane_copies_the_user_presentation_table(tmp_path):
    planes = copy_contract.configured_planes(
        execution_source=tmp_path / "execution.db", execution_destination="postgresql://local/execution",
        research_source=tmp_path / "research.db", research_destination="postgresql://local/research",
        ledger_source=tmp_path / "ledger.db", ledger_destination="postgresql://local/ledger")
    execution = next(plane for plane in planes if plane.name == "execution")
    assert "chart_context_annotations" in execution.metadata.tables


def test_postgresql16_clean_target_restore_preserves_annotation_identity(pg_sandbox, tmp_path):
    dump_tool = shutil.which("pg_dump") or next(iter(Path("/opt/homebrew/Cellar/postgresql@16").glob("*/bin/pg_dump")), None)
    restore_tool = shutil.which("pg_restore") or next(iter(Path("/opt/homebrew/Cellar/postgresql@16").glob("*/bin/pg_restore")), None)
    if dump_tool is None or restore_tool is None:
        pytest.skip("PostgreSQL 16 dump/restore tools are unavailable")
    source_url = pg_sandbox.url("chart_restore_source")
    target_url = pg_sandbox.url("chart_restore_target")
    source = pg_sandbox.engine("chart_restore_source")
    Base.metadata.create_all(source)
    with source.begin() as connection:
        command.stamp(migrate.alembic_config(connection), "0051", purge=True)
    geometry = Level("100")
    applicability = CausalApplicability(
        dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 1, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 2, tzinfo=UTC))
    now = dt.datetime(2026, 1, 1, 10, 0)
    with Session(source) as session:
        session.add(Organization(organization_id="owner.restore", name="Restore"))
        session.flush()
        session.add(ChartContextAnnotation(owner_id="owner.restore",
            market_context_address=identity().market_context_address,
            annotation_id="00000000-0000-0000-0000-000000000001", revision=1,
            dataset_manifest_address=identity().dataset_manifest_address,
            canonical_instrument_address=identity().canonical_instrument_address,
            timeframe_seconds=60, geometry_address=geometry.address,
            geometry_json=geometry.canonical_bytes.decode(),
            applicability_address=applicability.address,
            applicability_json=applicability.canonical_bytes.decode(), created_at=now,
            updated_at=now))
        session.commit()
    artifact = tmp_path / "chart-context.dump"
    dump_url = source_url.replace("postgresql+psycopg://", "postgresql://")
    restore_url = target_url.replace("postgresql+psycopg://", "postgresql://")
    subprocess.run([str(dump_tool), "--format=custom", "--file", str(artifact), dump_url],
                   check=True, capture_output=True, text=True)
    subprocess.run([str(restore_tool), "--dbname", restore_url, str(artifact)],
                   check=True, capture_output=True, text=True)
    target = pg_sandbox.engine("chart_restore_target")
    assert migrate.schema_version(target) == "0051"
    with Session(target) as session:
        row = session.get(ChartContextAnnotation,
            (identity().owner_id, identity().market_context_address,
             "00000000-0000-0000-0000-000000000001"))
        assert (row.geometry_address, row.geometry_json, row.revision) == (
            geometry.address, geometry.canonical_bytes.decode(), 1)
        copy_contract._validate_content_addresses(session.connection(), Base.metadata)


def test_postgresql16_copy_and_restore_validation_refuse_257_valid_rows(pg_sandbox):
    database_url = pg_sandbox.url("chart_restore_over_limit")
    with pg_sandbox.engine("chart_restore_over_limit").begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA execution")
    source_url = database_url + "?options=-csearch_path%3Dexecution"
    source = sa.create_engine(source_url, future=True)
    Base.metadata.create_all(source)
    with source.begin() as connection:
        command.stamp(migrate.alembic_config(connection), "0051", purge=True)
    geometry = Level("100")
    applicability = CausalApplicability(
        dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 1, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 2, tzinfo=UTC))
    now = dt.datetime(2026, 1, 1, 10, 0)
    with Session(source) as session:
        session.add(Organization(organization_id="owner.restore", name="Restore"))
        session.flush()
        first = ChartContextAnnotation(owner_id="owner.restore",
            market_context_address=identity().market_context_address,
            annotation_id="00000000-0000-0000-0000-000000000001", revision=1,
            dataset_manifest_address=identity().dataset_manifest_address,
            canonical_instrument_address=identity().canonical_instrument_address,
            timeframe_seconds=60, geometry_address=geometry.address,
            geometry_json=geometry.canonical_bytes.decode(),
            applicability_address=applicability.address,
            applicability_json=applicability.canonical_bytes.decode(), created_at=now,
            updated_at=now)
        session.add(first); session.flush(); fill_annotation_group(session, source=first)
        session.commit()
    with source.connect() as connection:
        with pytest.raises(copy_contract.CopyRefusal, match="presentation ceiling"):
            copy_contract._validate_content_addresses(connection, Base.metadata)
    execution = next(plane for plane in restore_contract.configured_restore_planes(
        execution_url=source_url, research_url=pg_sandbox.url("unused_research"),
        ledger_url=pg_sandbox.url("unused_ledger")) if plane.name == "execution")
    with pytest.raises(restore_contract.RestoreRefusal, match="current PostgreSQL validation failed"):
        restore_contract._plane_evidence(execution, generation_id="generation.overlimit",
            artifact={"identifier": "synthetic", "sha256": "0" * 64}, batch_size=500)
    with Session(source) as session:
        assert session.query(ChartContextAnnotation).count() == 257
    source.dispose()


def test_postgresql16_copy_rolls_back_257_valid_rows(pg_sandbox, tmp_path):
    sqlite_path = tmp_path / "execution-over-limit.db"
    sqlite_engine = sa.create_engine(f"sqlite+pysqlite:///{sqlite_path}", future=True)
    Base.metadata.create_all(sqlite_engine)
    with sqlite_engine.begin() as connection:
        command.stamp(migrate.alembic_config(connection), "0051", purge=True)
    geometry = Level("100")
    applicability = CausalApplicability(
        dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 1, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 2, tzinfo=UTC))
    now = dt.datetime(2026, 1, 1, 10, 0)
    with Session(sqlite_engine) as session:
        session.add(Organization(organization_id="owner.restore", name="Restore"))
        session.flush()
        first = ChartContextAnnotation(owner_id="owner.restore",
            market_context_address=identity().market_context_address,
            annotation_id="00000000-0000-0000-0000-000000000001", revision=1,
            dataset_manifest_address=identity().dataset_manifest_address,
            canonical_instrument_address=identity().canonical_instrument_address,
            timeframe_seconds=60, geometry_address=geometry.address,
            geometry_json=geometry.canonical_bytes.decode(),
            applicability_address=applicability.address,
            applicability_json=applicability.canonical_bytes.decode(), created_at=now,
            updated_at=now)
        session.add(first); session.flush(); fill_annotation_group(session, source=first)
        session.commit()
    destination_database = pg_sandbox.url("chart_copy_over_limit")
    with pg_sandbox.engine("chart_copy_over_limit").begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA execution")
    destination_url = destination_database + "?options=-csearch_path%3Dexecution"
    execution = next(plane for plane in copy_contract.configured_planes(
        execution_source=sqlite_path, execution_destination=destination_url,
        research_source=tmp_path / "unused-research.db",
        research_destination=pg_sandbox.url("unused_copy_research"),
        ledger_source=tmp_path / "unused-ledger.db",
        ledger_destination=pg_sandbox.url("unused_copy_ledger")) if plane.name == "execution")
    with pytest.raises(copy_contract.CopyRefusal, match="presentation ceiling"):
        copy_contract._copy_one(execution, batch_size=100)
    target = sa.create_engine(destination_url, future=True)
    with target.connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(
            ChartContextAnnotation.__table__)) == 0
    with Session(sqlite_engine) as session:
        assert session.query(ChartContextAnnotation).count() == 257
    target.dispose(); sqlite_engine.dispose()
