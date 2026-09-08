from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa


ROOT = Path(__file__).parents[1]


def test_chart_context_has_no_provider_execution_or_monitoring_imports():
    paths = [ROOT / "app/chart/annotation_context.py", ROOT / "app/chart/annotation_repository.py",
             ROOT / "app/api/chart_context_routes.py"]
    text = "\n".join(path.read_text() for path in paths)
    for forbidden in ("app.providers", "app.engine", "app.execution", "app.monitoring",
                      "research.domain"):
        assert forbidden not in text


def test_product_error_copy_never_contains_forbidden_protocol_term():
    text = (ROOT / "app/api/chart_context_routes.py").read_text().lower()
    rendered_literals = [line for line in text.splitlines() if "message\"" in line]
    assert all("canonical" not in line for line in rendered_literals)


def test_monitoring_schema_accepts_exact_additive_heads_and_refuses_unknown_or_multihead(tmp_path):
    from app.monitoring.repository import (
        MonitoringCorrupt, monitoring_schema_manifest, validate_monitoring_schema,
    )
    from tests.test_v0_monitoring_persistence import _engine

    engine = _engine(tmp_path, "monitoring-compatible-heads.db")
    with engine.begin() as connection:
        baseline = monitoring_schema_manifest(connection)
        for head in ("0049", "0050", "0051"):
            connection.exec_driver_sql("DELETE FROM alembic_version")
            connection.execute(sa.text(
                "INSERT INTO alembic_version(version_num) VALUES (:head)"), {"head": head})
            validate_monitoring_schema(connection)
            assert monitoring_schema_manifest(connection) == baseline
        connection.exec_driver_sql("DELETE FROM alembic_version")
        connection.exec_driver_sql("INSERT INTO alembic_version(version_num) VALUES ('9999')")
        with pytest.raises(MonitoringCorrupt, match="one exact compatible"):
            validate_monitoring_schema(connection)
        connection.exec_driver_sql("DELETE FROM alembic_version")
        connection.exec_driver_sql(
            "INSERT INTO alembic_version(version_num) VALUES ('0050'),('0051')")
        with pytest.raises(MonitoringCorrupt, match="one exact compatible"):
            validate_monitoring_schema(connection)
