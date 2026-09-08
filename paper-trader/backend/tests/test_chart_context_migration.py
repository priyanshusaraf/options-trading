from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

import sqlalchemy as sa
import pytest
from alembic import command
from sqlalchemy.orm import Session

from app.db import migrate
from app.db.models import Base, ChartContextAnnotation, Organization


def test_head_is_linear_0050_to_0051():
    script = migrate.ScriptDirectory.from_config(migrate.alembic_config())
    revision = script.get_revision("0051")
    assert revision.down_revision == "0050"
    assert script.get_revision("0052").down_revision == "0051"
    assert script.get_revision("0053").down_revision == "0052"
    assert script.get_revision("0054").down_revision == "0053"
    assert script.get_revision("0055").down_revision == "0054"
    assert script.get_revision("0056").down_revision == "0055"
    assert script.get_heads() == ["0056"]


def test_empty_install_and_restart_match_model(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'empty.db'}", future=True)
    migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine),
                        legacy_migrate=lambda: None, expected_tables=Base.metadata.tables)
    assert migrate.schema_version(engine) == "0056"
    assert set(sa.inspect(engine).get_columns("chart_context_annotations")[0]) >= {"name"}
    assert migrate.upgrade_to_head(engine) == "0056"
    assert {column.name for column in ChartContextAnnotation.__table__.columns} == {
        column["name"] for column in sa.inspect(engine).get_columns("chart_context_annotations")}
    engine.dispose()


@pytest.fixture(autouse=True)
def historical_chart_migration_target(request, monkeypatch):
    """Keep the 0050→0051 migration checks explicit after later additive heads."""
    if request.node.name in {"test_head_is_linear_0050_to_0051", "test_empty_install_and_restart_match_model"}:
        return
    upgrade = command.upgrade
    monkeypatch.setattr(migrate, "head_revision", lambda: "0051")
    monkeypatch.setattr(command, "upgrade", lambda config, target: upgrade(config, "0051" if target == "head" else target))


def test_exact_0050_upgrade_and_empty_downgrade(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'upgrade.db'}", future=True)
    Base.metadata.create_all(engine)
    ChartContextAnnotation.__table__.drop(engine)
    with engine.begin() as connection:
        command.stamp(migrate.alembic_config(connection), "0050", purge=True)
    assert "chart_context_annotations" not in sa.inspect(engine).get_table_names()
    assert migrate.schema_version(engine) == "0050"
    assert migrate.schema_version(engine) == "0050"
    assert migrate.upgrade_to_head(engine) == "0051"
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0050")
    assert "chart_context_annotations" not in sa.inspect(engine).get_table_names()
    engine.dispose()


def test_populated_0051_refuses_lossy_downgrade_and_preserves_row(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'populated.db'}", future=True)
    migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine),
                        legacy_migrate=lambda: None, expected_tables=Base.metadata.tables)
    now = __import__("datetime").datetime.now()
    with Session(engine) as session:
        session.add(Organization(organization_id="owner.migration", name="Migration"))
        session.add(ChartContextAnnotation(owner_id="owner.migration",
            market_context_address="sha256:" + "a" * 64,
            annotation_id="00000000-0000-0000-0000-000000000001", revision=1,
            dataset_manifest_address="sha256:" + "b" * 64,
            canonical_instrument_address="sha256:" + "c" * 64, timeframe_seconds=60,
            geometry_address="sha256:" + "d" * 64,
            geometry_json='{"kind":"LEVEL","price":"100","schema":"normalized-annotation-geometry/1"}',
            applicability_address="sha256:" + "e" * 64,
            applicability_json='{"effective_from":"2026-01-01T09:02:00.000000+00:00","effective_to":null,"known_at":"2026-01-01T09:00:00.000000+00:00","locked_at":"2026-01-01T09:01:00.000000+00:00","schema":"annotation-applicability/1"}',
            created_at=now, updated_at=now))
        session.commit()
    with engine.begin() as connection:
        with pytest.raises(RuntimeError, match="refuses to discard annotation rows"):
            command.downgrade(migrate.alembic_config(connection), "0050")
    assert migrate.schema_version(engine) == "0051"
    with Session(engine) as session:
        assert session.query(ChartContextAnnotation).count() == 1
    engine.dispose()


def _postgresql_0050_without_annotations(engine):
    Base.metadata.create_all(engine)
    ChartContextAnnotation.__table__.drop(engine)
    with engine.begin() as connection:
        command.stamp(migrate.alembic_config(connection), "0050", purge=True)


def test_postgresql16_exact_upgrade_restart_and_model_parity(pg_sandbox):
    engine = pg_sandbox.engine("chart_context_0051")
    _postgresql_0050_without_annotations(engine)
    assert migrate.upgrade_to_head(engine) == "0051"
    assert migrate.upgrade_to_head(engine) == "0051"
    columns = {column["name"] for column in sa.inspect(engine).get_columns(
        "chart_context_annotations")}
    assert columns == {column.name for column in ChartContextAnnotation.__table__.columns}
    indexes = sa.inspect(engine).get_indexes("chart_context_annotations")
    assert any(index["column_names"][:2] == ["owner_id", "market_context_address"]
               for index in indexes)


def test_postgresql16_concurrent_0051_owners_serialize_and_refuse(pg_sandbox):
    engine = pg_sandbox.engine("chart_context_0051_concurrent")
    _postgresql_0050_without_annotations(engine)
    barrier = threading.Barrier(2)

    def migrate_once():
        barrier.wait(timeout=10)
        try:
            return "RETURNED", migrate.upgrade_to_head(engine)
        except RuntimeError as exc:
            return "REFUSED", str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _item: migrate_once(), range(2)))
    assert sorted(result[0] for result in results) == ["REFUSED", "RETURNED"]
    assert ("RETURNED", "0051") in results
    assert any("concurrent migration owner" in detail for kind, detail in results
               if kind == "REFUSED")
    assert migrate.schema_version(engine) == "0051"
