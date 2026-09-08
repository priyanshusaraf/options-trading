"""Current-byte adoption guards for research authority transaction seams."""
from __future__ import annotations

from pathlib import Path

import os
import uuid
from datetime import timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session


def test_every_classified_research_seam_uses_the_shared_boundary() -> None:
    backend = Path(__file__).resolve().parents[1]
    expected = {
        "research/domain/admissions.py": "research_strategy_admission",
        "research/domain/strategy_admissions.py": "research_dataset_authority",
        "app/backtest/repository.py": "backtest_complete_claim",
    }
    for relative, scope in expected.items():
        source = (backend / relative).read_text()
        assert f'caller_owned_savepoint(session, scope="{scope}")' in source


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_dataset_authority_seam_leaves_no_postgresql_manifest_after_caller_rollback() -> None:
    """Use separate disposable execution/research schemas for the real seam."""
    from app.db.models import Base
    from research.domain.base import ResearchBase
    from research.domain.models import ResearchDatasetManifestV2
    from research.domain.strategy_admissions import persist_verified_dataset_authority
    from tests.test_phase4_dataset_assessment_authority import T0, _authority, _seed_execution

    url = os.environ["PT_TEST_POSTGRES_URL"]
    execution_schema = f"phase4_exec_{uuid.uuid4().hex}"
    research_schema = f"phase4_research_{uuid.uuid4().hex}"
    admin = sa.create_engine(url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{execution_schema}"'))
        connection.execute(sa.text(f'CREATE SCHEMA "{research_schema}"'))
    execution = sa.create_engine(url, future=True,
                                 connect_args={"options": f"-csearch_path={execution_schema}"})
    research = sa.create_engine(url, future=True,
                                connect_args={"options": f"-csearch_path={research_schema}"})
    try:
        Base.metadata.create_all(execution)
        ResearchBase.metadata.create_all(research)
        with Session(execution) as execution_session, Session(research) as research_session:
            values = _seed_execution(execution_session)
            manifest, segments = _authority(values)
            persist_verified_dataset_authority(
                research_session, manifest=manifest, segments=segments,
                execution_session=execution_session, at_time=T0 + timedelta(hours=3))
            research_session.rollback()
        with Session(research) as observer:
            assert observer.get(
                ResearchDatasetManifestV2, (manifest.owner_id, manifest.manifest_address)
            ) is None
    finally:
        execution.dispose()
        research.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{execution_schema}" CASCADE'))
            connection.execute(sa.text(f'DROP SCHEMA "{research_schema}" CASCADE'))
        admin.dispose()


@pytest.mark.parametrize("outcome", ["rollback", "commit-refusal"])
def test_dataset_authority_real_writer_leaves_no_sqlite_rows_after_caller_failure(outcome: str) -> None:
    """Segments, manifest and links have exactly the caller's SQLite fate."""
    from sqlalchemy import event
    from app.db.models import Base
    from research.domain.base import ResearchBase
    from research.domain.models import (ResearchDatasetManifestSegmentV2,
                                        ResearchDatasetManifestV2,
                                        ResearchDatasetSegmentV2)
    from research.domain.strategy_admissions import persist_verified_dataset_authority
    from tests.test_phase4_dataset_assessment_authority import T0, _authority, _seed_execution

    execution = sa.create_engine("sqlite://", future=True)
    research = sa.create_engine("sqlite://", future=True)
    Base.metadata.create_all(execution)
    ResearchBase.metadata.create_all(research)
    def refuse_commit(connection):
        if connection.engine is research:
            raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)
    if outcome == "commit-refusal":
        event.listen(research, "commit", refuse_commit)
    try:
        with Session(execution) as execution_session, Session(research) as research_session:
            values = _seed_execution(execution_session)
            execution_session.commit()
            manifest, segments = _authority(values)
            persist_verified_dataset_authority(
                research_session, manifest=manifest, segments=segments,
                execution_session=execution_session, at_time=T0 + timedelta(hours=3))
            if outcome == "rollback":
                research_session.rollback()
            else:
                with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                    research_session.commit()
                research_session.rollback()
        with Session(research) as observer:
            assert observer.scalar(sa.select(sa.func.count()).select_from(
                ResearchDatasetSegmentV2).where(ResearchDatasetSegmentV2.owner_id == manifest.owner_id)) == 0
            assert observer.scalar(sa.select(sa.func.count()).select_from(
                ResearchDatasetManifestV2).where(ResearchDatasetManifestV2.owner_id == manifest.owner_id)) == 0
            assert observer.scalar(sa.select(sa.func.count()).select_from(
                ResearchDatasetManifestSegmentV2).where(
                    ResearchDatasetManifestSegmentV2.owner_id == manifest.owner_id)) == 0
    finally:
        if outcome == "commit-refusal":
            event.remove(research, "commit", refuse_commit)
        execution.dispose()
        research.dispose()


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="PT_TEST_POSTGRES_URL is not configured")
def test_dataset_authority_real_writer_postgresql_commit_refusal_leaves_no_rows() -> None:
    from sqlalchemy import event
    from app.db.models import Base
    from research.domain.base import ResearchBase
    from research.domain.models import (ResearchDatasetManifestSegmentV2,
                                        ResearchDatasetManifestV2,
                                        ResearchDatasetSegmentV2)
    from research.domain.strategy_admissions import persist_verified_dataset_authority
    from tests.test_phase4_dataset_assessment_authority import T0, _authority, _seed_execution

    url = os.environ["PT_TEST_POSTGRES_URL"]
    execution_schema = f"phase4_exec_refusal_{uuid.uuid4().hex}"
    research_schema = f"phase4_research_refusal_{uuid.uuid4().hex}"
    admin = sa.create_engine(url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{execution_schema}"'))
        connection.execute(sa.text(f'CREATE SCHEMA "{research_schema}"'))
    execution = sa.create_engine(url, future=True,
                                 connect_args={"options": f"-csearch_path={execution_schema}"})
    research = sa.create_engine(url, future=True,
                                connect_args={"options": f"-csearch_path={research_schema}"})
    def refuse_commit(connection):
        if connection.engine is research:
            raise sa.exc.DBAPIError.instance("COMMIT", {}, RuntimeError("commit refusal"), RuntimeError)
    try:
        Base.metadata.create_all(execution)
        ResearchBase.metadata.create_all(research)
        with Session(execution) as execution_session, Session(research) as research_session:
            values = _seed_execution(execution_session)
            execution_session.commit()
            manifest, segments = _authority(values)
            persist_verified_dataset_authority(research_session, manifest=manifest, segments=segments,
                                               execution_session=execution_session,
                                               at_time=T0 + timedelta(hours=3))
            event.listen(research, "commit", refuse_commit)
            with pytest.raises(sa.exc.DBAPIError, match="commit refusal"):
                research_session.commit()
            research_session.rollback()
        with Session(research) as observer:
            for model in (ResearchDatasetSegmentV2, ResearchDatasetManifestV2,
                          ResearchDatasetManifestSegmentV2):
                assert observer.scalar(sa.select(sa.func.count()).select_from(model).where(
                    model.owner_id == manifest.owner_id)) == 0
    finally:
        event.remove(research, "commit", refuse_commit)
        execution.dispose()
        research.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{execution_schema}" CASCADE'))
            connection.execute(sa.text(f'DROP SCHEMA "{research_schema}" CASCADE'))
        admin.dispose()
